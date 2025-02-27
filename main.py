
"""
# Setup
1. Create a tab in hydrus called "HFH"
2. Change Settings here below as you like, dont forget to provide a API Key and IP
3. populate and alter the tagscore table using something like "DB Browser for SQLite"
4. Execute the code and happy archiving!
"""

api_url = "APIURL"
access_key = "YOUR API KEY"
populate_db_with_examples = True # set to True to get some example data into your db
whitelist = ["system:inbox", "system:filetype is animation, image, video"]  # will be put at the end of all queries
blacklist = ["gore"]  # will get a - in front of all tags and also added to all queries
tabname = "HFH"
limit = 1024
default_score = 0.1 # tags without a score will be tagged with this

# import
import hydrus_api, hydrus_api.utils # tested with V4.0.0
import sqlite3
from tqdm import tqdm

def InitializeDatabase():
    try:
        # Connect to the SQLite database (or create it if it doesn't exist)
        mydb = sqlite3.connect('db.db')
        cmydb = mydb.cursor()

        # Check if the table already exists
        cmydb.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='TagScores'")
        table_exists = cmydb.fetchone()

        if not table_exists:
            print("Creating Database")
            # Create the table if it does not exist
            cmydb.execute("""
                CREATE TABLE TagScores (
                    tag TEXT,
                    score REAL,
                    siblings TEXT,
                    comment TEXT
                )
            """)
            print("Table created.")
        else:
            print("Table already exists.")

        # Commit the changes
        mydb.commit()
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        # Close the connection
        mydb.close()

def ExamplePopulation():
    try:
        # Connect to the SQLite database
        mydb = sqlite3.connect('db.db')
        cmydb = mydb.cursor()

        # Define example data
        example_data = [
            ('samus aran', 0.3, None, None),
            ('elf', 0.2, None, "give positive score to things you like"),
            ('blood', -1.0, None, 'go negative for things you dont like, think how much good stuff it would need to balance it, go high for really bad stuff'),
            ('system:has audio', 0.1, None, None),
            ('system:ratio = 16:9', 0.1, None, 'I like files that fit my screen well'),
            ('science fiction', 0.2, None, '*spaceship noises*'),
            ('computer', 0.1, None, 'computer for the win!'),
            ('monochrome', -0.1, None, 'Why does it burn when I see?'),
            ('greyscale', -0.1, None, 'Why does it burn when I see?'),
            ('system:has transparency', -0.1, None, 'transparency can be annoying'),
            ('system:width = 3,840', 0.1, None, 'prefer 4k files'),
            ('system:height = 2,160', 0.1, None, 'prefer 4k files')
        ]

        # Get existing tags from the database
        cmydb.execute('SELECT tag FROM TagScores')
        existing_tags = set([row[0] for row in cmydb.fetchall()])

        # Filter out tags that already exist
        new_data = [data for data in example_data if data[0] not in existing_tags]

        # Insert new data into the table
        if new_data:
            cmydb.executemany("""
                INSERT INTO TagScores (tag, score, siblings, comment) VALUES (?, ?, ?, ?)
            """, new_data)
            print("New example data inserted.")
        else:
            print("No new example data to insert.")

        # Commit the changes
        mydb.commit()
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        # Close the connection
        mydb.close()

def DBHighScoreArchiver(client, blacklist, whitelist, limit, tabname="HFH"):

    def find_page_key(tabs, tabname):
        if 'pages' in tabs and isinstance(tabs['pages'], list):
            for page in tabs['pages']:
                if page.get('name') == tabname:
                    return page.get('page_key')
                if 'pages' in page and isinstance(page['pages'], list):
                    sub_page_key = find_page_key(page, tabname)
                    if sub_page_key:
                        return sub_page_key
        return None

    def DisplayFileIDs(tabname, fileIDs, focus=True):
        client = hydrus_api.Client(access_key=access_key, api_url=api_url)
        tabs = client.get_pages()
        page_key = find_page_key(tabs, tabname)
        if not page_key:
            print(f"No Tabkey found, you have to create the tab called {tabname}")
        else:
            client.add_files_to_page(page_key=page_key, file_ids=fileIDs)
            if focus:
                client.focus_page(page_key)

    # processing blacklist
    for tag in blacklist:
        blacklist[blacklist.index(tag)] = "-" + tag

    # Retrieve the tags and their manually set scores from the database
    mydb = sqlite3.connect('db.db')
    cmydb = mydb.cursor()

    cmydb.execute('SELECT tag, score FROM TagScores')
    db_tags = cmydb.fetchall()

    # Initialize an empty dictionary to store file IDs and their scores
    ScoreAndIDs = {}

    # Initialize a progress bar with the total number of iterations
    pbar = tqdm(total=len(db_tags), desc="Processing DB Tags", miniters=10, ncols=80)

    # Loop through each tag in the database
    tag_list = blacklist + whitelist
    for tag, score in db_tags:
        if score is None:
            # Set a manual score for all tags that have no score in the database
            score = default_score

        query = [tag] + tag_list  # here we can reduce one merge option by doing it earlier
        file_ids = client.search_files(query, file_sort_type=13)  # returns fileids


        # Store each file ID in the ScoreAndIDs dictionary with the manually set score
        for file_id in file_ids:
            if file_id not in ScoreAndIDs:
                ScoreAndIDs[file_id] = score
            else:
                # Increment the score by 0.2 (i.e., add 0.1 to its current score)
                ScoreAndIDs[file_id] += score

        # Update the progress bar
        pbar.update(1)

    # Sort the file IDs by their scores in descending order

    sorted_file_ids = sorted(ScoreAndIDs.items(), key=lambda x: x[1], reverse=True)

    # Return a list of the top
    top_file_ids = [file_id for file_id, score in sorted_file_ids[:limit]]
    DisplayFileIDs(tabname, top_file_ids)
    # return [file_id for file_id, score in sorted_file_ids[:limit]]
    cmydb.close()


if __name__ == '__main__':
    InitializeDatabase()
    if populate_db_with_examples:
        ExamplePopulation()
    client = hydrus_api.Client(access_key=access_key, api_url=api_url)
    DBHighScoreArchiver(client, blacklist, whitelist, limit=1024, tabname=tabname)