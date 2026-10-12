import json
import mysql.connector
from snowflake.sqlalchemy import URL

# Load MySQL database configuration from JSON file
with open('mysql_config.json') as f:
    mysql_config = json.load(f)

# Establish connection to MySQL database
cnx = mysql.connector.connect(**mysql_config)

# Create a cursor object
cursor = cnx.cursor()

# SQL query to fetch data from MySQL database
query = "SELECT * FROM table_name"

# Execute the query and fetch all rows
cursor.execute(query)
rows = cursor.fetchall()

# Close the cursor and connection objects
cursor.close()
cnx.close()

# Establish connection to Snowflake database using SQLAlchemy URL
url = URL(username='your_username', password='your_password', account='your_account', warehouse='your_warehouse', database='your_database', schema='your_schema')
engine = url.create_engine()

# Create a session object
session = engine.connect()

# SQL query to upsert data in Snowflake table
query = "INSERT INTO table_name (column1, column2, record_type) VALUES (%s, %s, 'i') ON DUPLICATE KEY UPDATE column1=VALUES(column1), column2=VALUES(column2), record_type='u'"

# Execute the query for each row fetched from MySQL database
for row in rows:
    session.execute(query, (row[0], row[1]))

# Commit the changes and close the session object
session.commit()
session.close()
