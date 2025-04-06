import os
import gspread
from google.oauth2.service_account import Credentials
import psycopg2
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import InputRequired
from werkzeug.security import check_password_hash
#from werkzeug.security import generate_password_hash
#need for add user route for admin

##HASH PASSWORDS

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your_default_secret_key')  # Set a default key for local testing

# Database configuration
DB_HOST = os.getenv("DB_HOST")  # Default to localhost for local testing
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Create a connection to PostgreSQL
def get_db_connection():
    print(f"++++++++++++++++++++++{DB_HOST}")
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    return conn

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired()])
    password = PasswordField('Password', validators=[InputRequired()])


def isloggedin():
    if 'user_id' not in session:
        return redirect(url_for('login'))

# Set up Google Sheets credentials
SCOPE = ['https://www.googleapis.com/auth/spreadsheets']
creds = Credentials.from_service_account_file('creds/credentials.json', scopes=SCOPE)

productSheet = "1kMzIO2-hISld-AiMqc_EhynN4-3onQ7ycjS0bpQjDdQ";
customerSheet = "1U4KVhMk_Oq7T4c1hvoj7K9YsR8xVMYawytbh0O45AT8";
sellerSheet = "1d9HMRlunMMumrmTm6tBlCK-kOBB6VNU4upZ1K9u1oy4";
salesSheet = "11hbwIBrc5omZ_1Qbs3VlyNpwR-kPcjQpOCX7RUdc-kI";


# Connect to Google Sheets
gc = gspread.authorize(creds)

def openSheet(SHEET_ID, SHEET_TAB):
    return gc.open_by_key(SHEET_ID).worksheet(SHEET_TAB)

# Fetch data from the Google Sheet
def get_sheet_data(SHEET_ID):
    # Open the spreadsheet
    sheet = gc.open_by_key(SHEET_ID).sheet1
    # Get all values from the sheet
    data = sheet.get_all_values()
    return data

def get_all_sheets_data(SHEET_ID):
    # Open the spreadsheet
    sheet = gc.open_by_key(SHEET_ID)
    # Get all worksheet names
    sheets_data = {ws.title: ws.get_all_values() for ws in sheet.worksheets()}
    print(sheets_data)
    return sheets_data

@app.route('/')
def index():
    # Get data from Google Sheet
    data = get_sheet_data(productSheet)
    # Render the template and pass the data to it
    return render_template('index.html', data=data)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        # Connect to the PostgreSQL database
        conn = get_db_connection()
        cur = conn.cursor()

        # Query the database for the user
        cur.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cur.fetchone()

        # Check if the user exists and if the password is correct
        if user and password:#check_password_hash(user[2], password):  # Assuming password is at index 2
            session['user_id'] = user[0]  # Store user ID in the session
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')

        # Close the database connection
        cur.close()
        conn.close()

    return render_template('login.html', form=form)

# Route for a simple dashboard after successful login
@app.route('/dashboard')
def dashboard():
    isloggedin()

    return render_template('dashboard.html')


@app.route('/sales')
def sales():
    isloggedin()

    data = get_sheet_data(salesSheet)
    return render_template('sales.html', data=data)

@app.route('/new')
def new():
    isloggedin()

    allProducts = {}
    productTypes = []
    customers,ckeys = remapData(get_sheet_data(customerSheet))
    #get products and remove out of stock items
    products = get_all_sheets_data(productSheet)
    for p in products:
        toDel = []
        productTypes.append(p)
        allProducts[p], pkeys = remapData(products[p])
        for stockCheck in allProducts[p]:
            if int(allProducts[p][stockCheck]['stock']) < 1:
                toDel.append(stockCheck)

        for d in toDel:
            #TODO - capture out od stock, items here
            del allProducts[p][d]
            
    print(allProducts)


    return render_template('new.html', ckeys = ckeys, customers=customers, products=allProducts, pkeys=pkeys, productTypes=productTypes)


@app.route('/updateStock', methods=['POST'])
def updateStock():
    isloggedin()
    data = request.get_json()
    print(data)

    prods = get_all_sheets_data(productSheet)

    matches = []
    for sheet in prods.items(): 
        for p,q in data['toPurchase'].items():
            for row in sheet:
                cellr = 0
                for c in row:
                    cellr += 1
                    if c[0] == p:
                        matches.append({'sheet': sheet[0], 'row': c, 'cellr':cellr, 'purchasedAmount':int(q)})
                        modSheetStock(matches[len(matches)-1])

    return "success"

    #return render_template('invoice.html')
  
def modSheetStock(match):
    print(match['row'])
    #TODO if matches >2 or <0 error
    #TODO if current stock < desired stock
    currentStock = int(match['row'][7]);
    print(f"cs {currentStock}")
    stock = openSheet(productSheet, match['sheet'])

    newqty = currentStock - match['purchasedAmount']
    stock.update_cell(match['cellr'], 8, newqty)

#take data from sheet, isolate header as keys list, map values of rets of sheet to object with keys
def remapData(data):
    remapped = {}
    keys = []
    num = 0
    for row in data:  # sheet_data is a list of dicts
        cnt = 0
        if not num:
            keys=row
            num = 1
        else:
            remapped[row[0]] = {}
            for k in keys:
                remapped[row[0]][k] = row[cnt]
                cnt+=1
    return remapped,keys

#edit customer
#add customer

if __name__ == '__main__':
    app.run(debug=True)
