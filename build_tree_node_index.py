import psycopg2
connection = None
cursor = None
try:
    connection = psycopg2.connect(user = "postgres",
                                password = "toor",
                                host = "127.0.0.1",
                                port = "5432",
                                database = "parabible")
    cursor = connection.cursor()
    cursor.execute("SELECT version();")
    record = cursor.fetchone()
except (Exception, psycopg2.DatabaseError) as e:
    print(e)

print("You are connected to - ", record,"\n")

# # Go through every node column and create:
# tree_node | wids
# 1         | [1,2,3,4,5]

column_names=[]
get_columns = """
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'word_features'
"""
try:
    cursor.execute(get_columns)
    column_name_results = cursor.fetchall()
    column_names = list(map(lambda x: x[0], column_name_results))
except (Exception, psycopg2.DatabaseError) as e:
    print(e)

node_columns = list(filter(lambda x: x.endswith("_node"), column_names))

create_table = f"""DROP TABLE IF EXISTS tree_node_index;
CREATE TABLE tree_node_index (
   nid integer NOT NULL,
   node_type TEXT NOT NULL,
   wids integer[] NOT NULL,
   PRIMARY KEY (nid, node_type)
);"""

try:
    cursor.execute(create_table)
    connection.commit()
except (Exception, psycopg2.DatabaseError) as e:
    print(e)


INSERTION_LIMIT = 50000
values_to_insert = []
def do_insert(insertion_values):
    values_string = ','.join(cursor.mogrify("(%s, %s, %s)", v).decode("utf-8") for v in insertion_values)

    insert_query = f"""
    INSERT INTO tree_node_index (nid, node_type, wids) VALUES {values_string}
    """
    print(insert_query[:100])
    cursor.execute(insert_query)
    connection.commit()
    
def insert_values(nid, node_type, wids):
    global values_to_insert
    values_to_insert.append((nid, node_type, wids))
    if (len(values_to_insert) >= INSERTION_LIMIT):
        to_insert = values_to_insert[:INSERTION_LIMIT]
        values_to_insert = values_to_insert[INSERTION_LIMIT:]
        do_insert(to_insert)

for node_type in node_columns:
    print(node_type.upper())
    wids_per_node = f"""
    SELECT DISTINCT {node_type}
    FROM word_features
    """
    cursor.execute(wids_per_node)
    nid_results = cursor.fetchall()
    nids_without_none = list(filter(lambda x: x[0] is not None, nid_results))
    nids = list(map(lambda x: int(x[0]), nids_without_none))

    for nid in nids:
        if nid is None: continue
        wid_query = f"""
        SELECT wid
        FROM word_features
        WHERE {node_type} = {nid}
        """
        cursor.execute(wid_query)
        wids_result = cursor.fetchall()
        wid_list = list(map(lambda x: int(x[0]), wids_result))
        wid_list_as_pg_string = str(wid_list).replace('[','{').replace(']','}')
        insert_values(nid, node_type, wid_list_as_pg_string)

    do_insert(values_to_insert)
    values_to_insert = []

connection.commit()


