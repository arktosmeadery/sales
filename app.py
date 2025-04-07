import os
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow

import psycopg2
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from pdfrw import PdfReader, PdfWriter, PageMerge, PdfDict, PdfObject
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import InputRequired
from werkzeug.security import check_password_hash
import datetime
import time

import smtplib
from email.message import EmailMessage


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
currentUser = False

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

productSheet = "1kMzIO2-hISld-AiMqc_EhynN4-3onQ7ycjS0bpQjDdQ"
customerSheet = "1U4KVhMk_Oq7T4c1hvoj7K9YsR8xVMYawytbh0O45AT8"
sellerSheet = "1d9HMRlunMMumrmTm6tBlCK-kOBB6VNU4upZ1K9u1oy4"
salesSheet = "11hbwIBrc5omZ_1Qbs3VlyNpwR-kPcjQpOCX7RUdc-kI"
invoiceFolder = "1tTbFL0a9jazDvuJXVaSfRaEcWglc0qOb"


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

def getRow(sheet, header, target):
    all_values = sheet.get_all_values()
    colnames = all_values[0]
    col_index = colnames.index(header)

    for i, row in enumerate(all_values[1:], start=2):  # start=2 because header is row 1
        if len(row) > col_index and row[col_index] == target:
            return row  # this is the 1-based row number in the sheet

    return None


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
            session['username'] = username
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


@app.route('/generate_invoice', methods=['POST'])
def generate_invoice():
    isloggedin()
    data = request.get_json()
    print(data)
    #TODO
    #get sale by saleID and then pass wot generate
    #generateInvoice(data['saleID'])

@app.route('/updateStock', methods=['POST'])
def updateStock():
    isloggedin()
    data = request.get_json()
    print(data)


    prods = get_all_sheets_data(productSheet)
    ts = time.time()
    
    loggedSales = []

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
                        loggedSales.append(addToSalesSheet(matches[len(matches)-1], ts, data['customerID']))
    
    invoiceLink = generateInvoice(ts, loggedSales, data['customerID'])
    return invoiceLink


def send_email_with_pdf(to_address, subject, body, pdf_path):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = 'arktosdistro@gmail.com'
    msg['To'] = to_address
    msg.set_content(body)

    # Attach PDF
    with open(pdf_path, 'rb') as f:
        pdf_data = f.read()
        msg.add_attachment(pdf_data, maintype='application', subtype='pdf', filename='arktosInvoice.pdf')

    # Send the email (Gmail example)
    '''
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login('your_email@example.com', 'your_password_or_app_password')
        smtp.send_message(msg)
    '''

def generateInvoice(ts, loggedSales, cid):
    isloggedin()
    print(f"LOGGED: {loggedSales}")
    #[{'sheet': 'MEAD_KEGS', 'row': ['mk1', 'Doc Holiday', 'Huckleberry', '7', '1/5 barrell', '500', '1', '1'], 'cellr': 2, 'purchasedAmount': 1}, 
    #{'sheet': 'MEAD_CANS', 'row': ['mc1', 'Doc Holiday', 'Huckleberry', '7', '12oz', '100', '6', '1', ''], 'cellr': 2, 'purchasedAmount': 3}]
    
    invoiceLink = 0
    #generateinvocie
    template_path = os.path.join(app.root_path, 'static', 'arktosInvoiceForm.pdf')
    output_path = os.path.join(app.root_path, "static", "filled.pdf")

    template_pdf = PdfReader(template_path)

    # Set NeedAppearances to true to ensure fields are visible
    if not template_pdf.Root.AcroForm:
        template_pdf.Root.AcroForm = PdfDict()

    template_pdf.Root.AcroForm.update(
        PdfDict(NeedAppearances=PdfObject('true'))
    )

    datetime_object = datetime.datetime.fromtimestamp(ts)
    formatted_date = datetime_object.strftime("%m/%d/%y")

    #get customer info for invoice
    customers = openSheet(customerSheet, 'activeCustomers')
    customer = getRow(customers, 'customerID', cid)

    FIELD_MAP = {
        'date': formatted_date,
        'saleID': ts,
        'customerName':customer[1],
        'address1':customer[3],
        'address2':customer[4],
        'seller':session['username'],
        'contact':customer[2],
        'phone':customer[5]
    }

    i = 1
    total = 0
    for sale in loggedSales:
        s = sale['sheet'] + ": "
        s += sale['row'][1] + " " + sale['row'][4]
        s += ' @$' + sale['row'][5]
        FIELD_MAP[f"item{i}"] = s
        FIELD_MAP[f"qty{i}"] = sale['purchasedAmount']
        linetotal = int(int(sale['purchasedAmount']) * int(sale['row'][5]))
        FIELD_MAP[f"total{i}"] = linetotal
        total += linetotal
        i += 1

    FIELD_MAP['total'] = total

    print(f"FIELDMAP \r\n{FIELD_MAP}")

    for page in template_pdf.pages:
        annotations = page.Annots
        if annotations:
            for annotation in annotations:
                if annotation.Subtype == "/Widget" and annotation.T:
                    key = annotation.T[1:-1]  # remove parentheses from the name
                    if key in FIELD_MAP:
                        annotation.update(
                            PdfDict(V='{}'.format(FIELD_MAP[key]))
                        )

    PdfWriter(output_path, trailer=template_pdf).write()

    #send pdf
    #send_email_with_pdf(customer[7], "Arktos Invoice", "Thank you for your business.", 'static/filled.pdf'):
    #rename pdf upload to drive
    #os.rename('static/filled.pdf', 'static/' + ts +'.pdf')
    #upload_to_drive('static/' + ts + '.pdf', invoiceFolder)
    #delete pdf from server
    #os.remove('static/' + ts + '.pdf')
    
    #return send_file(output_path, as_attachment=True)
    
    return 'success'


def addToSalesSheet(sale,ts,cid):

    print(f"sale {sale}")
    print(ts)
    print(cid)
    print(datetime.datetime.now().strftime("%Y"))
    sales = openSheet(salesSheet, datetime.datetime.now().strftime("%Y"))
    newrow = [
    datetime.datetime.now().strftime("%m/%d/%Y"),
    ts,
    cid,
    session['user_id'],
    sale['row'][1],
    sale['row'][0],
    sale['purchasedAmount'],
    sale['row'][5],
    round(int(sale['purchasedAmount']) * float(sale['row'][5]),2)
    ]

    print(newrow)
    sales.append_row(newrow)

    return sale


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


SCOPES = ['https://www.googleapis.com/auth/drive.file']
def upload_to_drive(pdf_path, folder_id):
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('drive', 'v3', credentials=creds)

    file_metadata = {
        'name': os.path.basename(pdf_path),
        'parents': [folder_id]  # Google Drive Folder ID
    }
    media = MediaFileUpload(pdf_path, mimetype='application/pdf')

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    print('File ID:', file.get('id'))

#edit customer
#add customer
#add user (admin page)
#archive user (admin page)

if __name__ == '__main__':
    app.run(debug=True)
