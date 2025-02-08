# HydrusForHydrus (HFH)
A set of tools and functions to improve your hydrus network experience.

## HighScoreArchiver
This tool allows you to track your favourite tags in a database and then it will present the files with the most and highest scored tags you set. Ideally allowing you to see the files you potentially are interested in the most.

This tool calculates the score for each file, based on the tags & scores your provided, then adds the top scoring files to the selected tab name in hydrus.

### Default Preperation 
1. Create a file search tab in hydrus called "HFH"
2. open the main.py and provide your API key and API IF of Hydrus.
3. let the script run, it will create the necessary database and add some example data, then send the results to hydrus for you to inspect.
4. open the .db file with something like "DB Viever for SQlite". If you wish edit or remove the example data. Add the tags you do like and don't like. Provide scores for each how much you like the tag, to express how much you like TagA more than TabB. Use negative scores to penalize tags you don't like, this will make them occure less often in the results.

install requirements:
`pip install -r requirements.txt`

### Install Dependencies
Install the required Python packages by running:
`pip install hydrus-api tqdm pyperclip `

### Tips
- highly recommended: use machine learning based image classification tool to tag your files first, to get even better results
- regularly update your TagScores table to reflect your preferences and new interests.
- Maintain your scores by sorting the table by score and ask yourself what should have a higher or lower score compared to similiar scored tags.
- use whitelist to filter results (default: system:inbox)
- use blacklist to remove files from the results

### Issues & Workarounds
- after the files get added to the tab, they are neither sorted* or collected (*they are actually sorted by score at that state) - so refresh the sorting and collecting by selecting "leave unmatched" then just select "leave unmatched" again, this will update the collections and sorting of files

## HighScoreArchiver UI Version
- no need for another tool to edit the data

### Controls
- when adding a tag it will check your clipboard and import the tag automatically
- use "+" and "-" to increas or decrease score by the set increment

### Future
- will add a status bar to show how long execution takes
