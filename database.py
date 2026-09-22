import sqlite3
from datetime import datetime

# Function to get the current price and 2 previous ones
def getPrice():
    # Connect to the database
    conn = sqlite3.connect('prices.db')
    c = conn.cursor()

    # Get the current date and time in UTC
    current_datetime = datetime.utcnow()

    # Format the date and time as a string
    if int(current_datetime.strftime("%M")) >= 30:
        time_string = f"{current_datetime.strftime('%H')}:30"
    else:
        time_string = f"{current_datetime.strftime('%H')}:00"

    # Initialize variables for tracking table and offset
    current_table = int(current_datetime.strftime('%d'))

    # Get the table name
    table_name = f"Day{current_table}"

    # Fetch the previous 2 records from the current table
    c.execute(f"SELECT * FROM {table_name} WHERE TimeUTC < '{time_string}' ORDER BY TimeUTC DESC LIMIT 2")
    data = c.fetchall()

    # Reorder the data if there are 2 records
    if len(data) == 2:
        temp = data[0]
        data[0] = data[1]
        data[1] = temp

    # Get the table name again
    table_name = f"Day{current_table}"

    # Determine the appropriate query based on the available data (24 records para 12 horas)
    if len(data) == 0:
        # No previous data, fetch 24 records from the current table
        c.execute(f"SELECT * FROM {table_name} WHERE TimeUTC >= '{time_string}' ORDER BY TimeUTC LIMIT 24")
    elif len(data) == 1:
        # Only 1 previous record, fetch 23 records from the current table
        c.execute(f"SELECT * FROM {table_name} WHERE TimeUTC >= '{time_string}' ORDER BY TimeUTC LIMIT 23")
    else:
        # Both previous records available, fetch 22 records from the current table
        c.execute(f"SELECT * FROM {table_name} WHERE TimeUTC >= '{time_string}' ORDER BY TimeUTC LIMIT 22")

    # Fetch the selected rows
    Ldata = c.fetchall()

    # Append the fetched rows to the data list
    for row in Ldata:
        data.append(row)

    # Check if additional records are needed from the next table
    if len(data) < 24:
        current_table += 1
        if current_table == 32:
            return data

        # Get the table name of the next table
        table_name = f"Day{current_table}"

        # Fetch the remaining rows from the next table
        c.execute(f"SELECT * FROM {table_name} ORDER BY TimeUTC LIMIT {24 - len(data)}")
        remRows = c.fetchall()

        # Append the remaining rows to the data list
        for row in remRows:
            data.append(row)

    # Close the connection
    conn.close()
    modified_data = []

    # Modify the data for formatting and emojis
    for row in data:
        row_list = list(row)
        
        if row_list[1] >= 600:
            row_list[1] = f"🟥 {row_list[1]}"
        else:
            row_list[1] = f"🟩 {row_list[1]}"
        
        if row_list[2] <= 130:
            row_list[2] = f"🟩 {row_list[2]}"
        else:
            row_list[2] = f"🟥 {row_list[2]}"
        
        modified_data.append(tuple(row_list))
    
    return modified_data


# Function to get the Daily Cheap Price
def getDailyPrice():
    # Connect to the database
    conn = sqlite3.connect('prices.db')
    c = conn.cursor()

    # Get the current date and time in UTC
    # Initialize variables for tracking table and offset
    current_day = int(datetime.utcnow().strftime('%d'))
    # Get the table name
    table_name = f"Day{current_day}"

    c.execute(f"SELECT * FROM {table_name} WHERE TimeUTC >= '00:00' AND (FuelPrice <= 550 OR CO2Price <=130)")
    data = c.fetchall()
        
    conn.close()      

    modified_data = []

    # Modify the data for formatting and emojis
    for row in data:
        row_list = list(row)
        if row_list[1] >= 600:
            row_list[1] = f"🟥 {row_list[1]}"
        else:
            row_list[1] = f"🟩 {row_list[1]}"
        
        if row_list[2] <= 130:
            row_list[2] = f"🟩 {row_list[2]}"
        else:
            row_list[2] = f"🟥 {row_list[2]}"
        
        modified_data.append(tuple(row_list))
    
    return modified_data, current_day

def getCurrentPrice():

    # connect to database
    conn = sqlite3.connect("prices.db")
    c = conn.cursor()

    # Get the current date and time in UTC
    current_datetime = datetime.utcnow()

    # Format the date and time as a string
    if int(current_datetime.strftime("%M")) >= 30:
        time_string = f"{current_datetime.strftime('%H')}:30"
    else:
        time_string = f"{current_datetime.strftime('%H')}:00"

    # Get the table name
    table_name = f"Day{int(current_datetime.strftime('%d'))}"

    # Fetch the previous 2 records from the current table
    c.execute(f"SELECT * FROM {table_name} WHERE TimeUTC == '{time_string}'")
    data = c.fetchone()

    conn.close()
    return data, table_name

def updateFuel(table_name, time, fuel):
    # connect to database
    conn = sqlite3.connect("prices.db")
    c = conn.cursor()

    c.execute(f"SELECT * FROM {table_name} WHERE TimeUTC == '{time}'")
    data = c.fetchone()

    c.execute(f"UPDATE {table_name} SET FuelPrice={fuel} WHERE TimeUTC == '{time}'")
    conn.commit()
    conn.close()
    statement = f"Successfully Updated fuel of {time} of {table_name} from {data[1]} to {fuel}"
    print(statement)
    return statement

def updateCO2(table_name, time, co2):
    # connect to database
    conn = sqlite3.connect("prices.db")
    c = conn.cursor()

    c.execute(f"SELECT * FROM {table_name} WHERE TimeUTC == '{time}'")
    data = c.fetchone()

    c.execute(f"UPDATE {table_name} SET CO2Price={co2} WHERE TimeUTC == '{time}'")
    conn.commit()
    conn.close()
    statement = f"Successfully Updated CO2 of {time} of {table_name} from {data[2]} to {co2}"
    print(statement)
    return statement

def updateBoth(table_name, time, fuel, co2):
    # connect to database
    conn = sqlite3.connect("prices.db")
    c = conn.cursor()

    c.execute(f"SELECT * FROM {table_name} WHERE TimeUTC == '{time}'")
    data = c.fetchone()

    c.execute(f"UPDATE {table_name} SET FuelPrice={fuel}, CO2Price={co2} WHERE TimeUTC == '{time}'")
    conn.commit()
    conn.close()
    statement = f"Successfully Updated Fuel and CO2 of {time} of {table_name} from {data[1]}, {data[2]} to {fuel}, {co2}"
    print(statement)
    return statement
