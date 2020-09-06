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



# # Go through every column and create:

# colname | value | node_type | json_array of wids (actual json col?)
# _sp     | verb  | phrase    | "[1,2,15,19]"
# _sp     | verb  | clause    | "[1,1,3,7]"
# ### - but how do we get to wids from this?

# OR
# colname | value | json_array of wids (actual json col?)
# _sp     | verb  | "[{clause: 1, phrase: 1, wid: 1},{clause: 1, phrase: 2, wid: 2},{clause: 3, phrase: 15, wid: 11},{clause: 11, phrase: 21, wid: 21}]"
### - but how do we get to wids from this?

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

# column overview:
# 1. wid                 => word id
# 2. features            => word features
# 3. _tc_note & _cf_wid  => these are for tc notes
# 4. xxxx_node           => tree node data
#
# i.e. let's remove all but (2)
def should_include_colummn(col_name):
    if col_name == "wid": return False
    if col_name == "_cf_wid": return False
    if col_name == "_tc_note": return False
    if col_name.endswith("_node"): return False
    return True

node_columns = list(filter(lambda x: x.endswith("_node"), column_names))
column_names = list(filter(should_include_colummn, column_names))
node_columns_sql = ", ".join(node_columns)



########################
### CREATE TABLE #######
########################
# create_node_columns = ", ".join(map(lambda x: x+" integer[]", node_columns))
# create_table = f"""DROP TABLE IF EXISTS feature_index;
# CREATE TABLE feature_index (
#     feature TEXT NOT NULL,
#     value TEXT NOT NULL,
#     wids integer[] NOT NULL,
#     {create_node_columns},
#     PRIMARY KEY (feature, value)
# );"""

create_table = f"""DROP TABLE IF EXISTS feature_index;
CREATE TABLE feature_index (
    feature TEXT NOT NULL,
    value TEXT NOT NULL,
    wids integer[] NOT NULL,
    PRIMARY KEY (feature, value)
);"""

try:
    cursor.execute(create_table)
    connection.commit()
except (Exception, psycopg2.DatabaseError) as e:
    print(e)




########################
### INSERT VALUES ######
########################

# expects (wid, ...node_columns_sql)
# def map_tuple_to_node_column_dict(word_node_tuple):
#     r = {
#         "wid": word_node_tuple[0]
#     }
#     for i, v in enumerate(node_columns, start=1):
#         r[v] = word_node_tuple[i]
#     return r

# column_names = ["_sp"]

import json
def unicode(text):
    return str(text, 'utf-8')
INSERTION_LIMIT = 50000
index_values = []
# The extra three here are for {feature, value, wid}
# If you want _node_columns, re-add this line and the one a bit lower down (with args_str) and the one that includes node_columns in columns_in_query
# mogrify_string = "(%s,%s,%s," + ",".join(map(lambda x: "%s", node_columns)) + ")"
mogrify_string = "(%s,%s,%s)"
def do_insert(insertion_values):
    args_str = ','.join(unicode(v) for v in (cursor.mogrify(mogrify_string, x) for x in insertion_values))
    # Here is the query string if you want _node_columns: INSERT INTO feature_index (feature, value, wids, {node_columns_sql}) VALUES {args_str}
    insert_query = f"""
    INSERT INTO feature_index (feature, value, wids) VALUES {args_str}
    """
    print(insert_query[:100])
    cursor.execute(insert_query)
    connection.commit()
def insert_index_values(new_values):
    global index_values
    index_values.append(new_values)
    if (len(index_values)) < INSERTION_LIMIT:
        return
    
    to_insert = index_values[:INSERTION_LIMIT]
    index_values = index_values[INSERTION_LIMIT:]
    do_insert(to_insert)

# column_names = ["_declension"]

for col in column_names:
    print(col.upper())
    unique_values_per_column = f"""
    SELECT DISTINCT {col}
    FROM word_features
    """
    cursor.execute(unique_values_per_column)
    results = cursor.fetchall()
    unique_values_per_column_list = list(map(lambda x: str(x[0]).replace("'", "''"), results))
    unique_values_per_column_list_without_nones = list(filter(lambda x: x != "None", unique_values_per_column_list))
    values = unique_values_per_column_list_without_nones

    print(col, len(values))
    for value in values:
        word_query = f"""
        SELECT wid, {node_columns_sql}
        FROM word_features
        WHERE {col} = '{value}'
        """
        cursor.execute(word_query)
        word_results = cursor.fetchall()

        # matching_set = list(map(map_tuple_to_node_column_dict, word_results))
        columns_in_query = ["wid"] #+ node_columns
        node_arrays_to_insert = [[row[i] for row in word_results] for i,c in enumerate(columns_in_query)]
        node_arrays_to_insert_without_nones = list(map(
            lambda nodes_of_type_list:
                list(map(lambda y: -1 if y is None else y, nodes_of_type_list)),
            node_arrays_to_insert))
        node_arrays_to_insert_as_pg_strings = map(lambda x: str(x).replace('[','{').replace(']','}'), node_arrays_to_insert_without_nones)

        new_value = (col, value,) + tuple(node_arrays_to_insert_as_pg_strings)
        # print(new_value)
        insert_index_values(new_value)

    do_insert(index_values)
    index_values = []

connection.commit()
print("creating index")
cursor.execute("CREATE INDEX feature_value_index ON feature_index USING btree (feature, value);")
print("creating intarray extension")
cursor.execute("CREATE EXTENSION IF NOT EXISTS intarray;")
connection.commit()
