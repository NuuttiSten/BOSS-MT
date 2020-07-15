
import numpy as np
import src.io.readwrite as rw
import src.parse.preprocess as preprocess
import os

# define all inputs and outputs

# RAW boss.out
RAW_wildcard = glob_wildcards('data/experiments/{raw_name}/boss.out')
RAW_NAME = RAW_wildcard.raw_name



## RULES
rule all:
    input:
        expand('processed_data/{raw_name}.json',
                raw_name = RAW_NAME)
        

# parse data from boss.out
rule parse_and_preprocess:
    input:
        'src/config/parse_and_preprocess/preprocess.yaml',
        expand('data/experiments/{raw_name}/boss.out',
                raw_name = RAW_NAME)
        
    output:
        expand('processed_data/{raw_name}.json',
                raw_name = RAW_NAME)
    run:
        # parse
        for infile, rawname, outfile in zip(input[1:], RAW_NAME, output):
            outfile = f'{outfile}'
            name = '_'.join(rawname.split('/exp_'))
            line = f'python3 src/parse/parse_BOSS_output.py {infile} {name} {outfile}'
            shell(line)

        # UNPREPROCESSED boss.out
        # detect folders
        PARSED_wildcard = glob_wildcards('processed_data/{exp_folder}/{exp_file}.json')
        PARSED_FOLDERS = np.unique(list(PARSED_wildcard.exp_folder))
        # detect files inside folders
        PARSED_FILELISTS = [] # list of lists of files inside each folder
        for folder in PARSED_FOLDERS:
            searchstring = ''.join([f'processed_data/{folder}/','{exp_file}.json'])
            parsed_filelist = glob_wildcards(searchstring).exp_file
            PARSED_FILELISTS.append(parsed_filelist)

        PARSED_DICT = {}
        for folder, filelist in zip(PARSED_FOLDERS, PARSED_FILELISTS):
            PARSED_DICT[folder] = filelist
        # preprocess
        config = rw.load_yaml('src/config/parse_and_preprocess/','preprocess.yaml')
        tolerances = config['tolerances']
        # baselines
        baselines = config['baselines']
        for folder in list(baselines.keys()): # loop through baselines
            print(folder)
            bestacqs = []
            get_truemin_from = baselines[folder]
            for filename in PARSED_DICT[get_truemin_from]: # load all baseline experiments
                print(filename)
                data = rw.load_json(f'processed_data/{folder}/',f'{filename}.json')
                bestacq = preprocess.get_bestacq(data)
                bestacqs.append(bestacq[-1])
            # select lowest observed value
            truemin = [min(bestacqs)]
            # save truemin ad y_offset and offset all y values accordingly
            for filename in PARSED_DICT[folder]: # load all baseline experiments
                data = rw.load_json(f'processed_data/{folder}/',f'{filename}.json')
                data['truemin'] = truemin
                data = preprocess.preprocess(data, tolerances)
                rw.save_json(data, f'processed_data/{folder}/',f'{filename}.json')
                    
        # other experiments
        experiments = config['experiments']
        for folder in list(experiments.keys()):
            truemin = []
            # read truemin values from baselines
            for baseline_folder in experiments[folder]:
                baseline_file = PARSED_DICT[baseline_folder][0]
                data = rw.load_json(f'processed_data/{baseline_folder}/',f'{baseline_file}.json')
                truemin.append(data['truemin'][0])
            # save truemin values to experiments
            for filename in PARSED_DICT[folder]:
                data = rw.load_json(f'processed_data/{folder}/',f'{filename}.json')
                data['truemin'] = truemin
                data = preprocess.preprocess(data, tolerances)
                rw.save_json(data, f'processed_data/{folder}/',f'{filename}.json')
            


            



