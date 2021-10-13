#import packages
import os
from datetime import datetime

#import mariadb
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from flask import (Flask, flash, redirect, render_template, request, send_file,
                   send_from_directory, url_for)
from flask_basicauth import BasicAuth
from wordcloud import STOPWORDS, WordCloud
import pandas as pd
#import mysql.connector
import mysql.connector

#Create App
app = Flask(__name__)

#load environmental variables
load_dotenv()

#set password for login
app.secret_key = os.environ.get('SECRETKEY')
app.config['BASIC_AUTH_USERNAME'] = os.environ.get('SITEUSER')
app.config['BASIC_AUTH_PASSWORD'] = os.environ.get('SITEPASS')
app.config['BASIC_AUTH_FORCE'] = True

basic_auth = BasicAuth(app)

#connects to database
def connect():
    mydb = mysql.connector.connect(
    user=os.environ.get('DATAUSER'),
    password=os.environ.get('DATAPASS'),
    host=os.environ.get('HOST'),
    database=os.environ.get('DATABASE'))
    print('connected')
    return mydb

#checks for latest entry_id in table
def check_last_entry_id():
    mydb = connect()
    cur = mydb.cursor()
    sql = 'SELECT ID FROM journal_entries ORDER BY ID DESC limit 1'
    cur.execute(sql)
    try:
        last_index = cur.fetchall()[0][0]
        print(last_index)
    except:
        last_index = 1
    close(mydb)
    return last_index

#closes connection
def close(mydb):
    mydb.close()
    print('closed')

#function that searches for text in entry using the navbar    
def search(cur):
    text = request.form['Keyword']
    sql_query = f"SELECT ID, Entry, Date FROM journal_entries \
    WHERE Entry LIKE '% {text} %' OR Entry LIKE '% {text}.%' OR Entry LIKE '{text} %' OR Entry LIKE '% {text},%' ORDER BY ID DESC "
    cur.execute(sql_query)
    rows = cur.fetchall()
    
    #hold sentences with keyword inside
    results = []
    ids = []
    dates = []
    oresults = []
    for row in rows:
        #grab the journal entry only
        sentences = row[1].split('.')
        for i,sentence in enumerate(sentences):
            if text in sentence:
                results.append(f"{sentences[i-1]}.{sentences[i]}.{sentences[i+1]}")
                break
        ids.append(row[0])
        dates.append(row[2])

    #create dataframe to hold information and return it
    df = pd.DataFrame()
    df['id'] = ids
    df['results'] = results
    df['date'] = dates
    return df

#show all entries in the journal    
@app.route('/',methods = ['GET', 'POST'])
def show_all():
    """ Queries sql table and show all results """
    mydb = connect()
    cur = mydb.cursor()
    sql_query = 'SELECT ID, Entry, Date FROM journal_entries ORDER BY ID DESC'
    cur.execute(sql_query)
    rows = cur.fetchall()
    

    if request.method == 'POST':
        df = search(cur)
        return render_template('results.html',data = df.values)

    return render_template('show_all.html', rows = rows )

#create a new entry in the journal
@app.route('/new', methods = ['GET', 'POST'])
def new():
    """ Add Entries to the table through text form """
    mydb = connect()
    cur = mydb.cursor()
    if request.method == 'POST':
      if not request.form['Entry']:
         flash('Please enter an Entry', 'error')
      else:
        entry_values = check_last_entry_id() + 1,request.form['Entry'],datetime.now().date()         
        sql = 'INSERT INTO journal.journal_entries(ID,Entry,Date)' 'VALUES(%s, %s, %s)'
        val = (entry_values)
        cur.execute(sql,val)
        mydb.commit()
        close(mydb)
        flash('Record was successfully added')
        return redirect(url_for('show_all'))
    return render_template('new.html')

#show sentences containing keywords
@app.route('/results')
def results():
    if request.method == 'POST':
        mydb = connect()
        cur = mydb.cursor()
        sql_query = 'SELECT ID, Entry, Date FROM journal_entries ORDER BY ID DESC'
        cur.execute(sql_query)
        df = search(cur)
        return render_template('results.html',data = df.values)
    
    return render_template('results.html')

@app.route('/wordcloud',methods=['POST','GET'])
def wordcloud():
    #variable to hold words in
    comment_words = ''

    #words not to include
    stopwords = ['feel','think','know','thing','really','t','s','m',
                'shouldn','don','people','someone','things','re','everyone','person','m',
                'isn','going','will','anything','doesn','today','didn','day',
                'goes','Friday','good','want','something','say','talking','time',
                'feeling','feel','felt','much','make','emotions','shouldn',
                'happened','ll','go','one','instead','even','see',
                'got','way','lot','ve','back','though','move',
                'still','anymore'] +list(STOPWORDS)
    #First do query of last x days as specified by user
    mydb = connect()
    cur = mydb.cursor()
    
    if request.method == 'POST':
      if not request.form['Word']:
         flash('Please enter an Entry', 'error')
      else:
        
        resp = request.form['Word']
        sql_query = f'SELECT ENTRY FROM journal_entries \
        WHERE Date  >= (DATE(NOW()) - INTERVAL {resp} DAY) \
        ORDER BY Date DESC'
        cur.execute(sql_query)
        rows = cur.fetchall()

        #combine all strings in query list to one big string
        for x in rows:
            comment_words+= ''.join(x) + ' '
        #create the word cloud
        wordcloud = WordCloud(width = 1000, height = 1000,
                        background_color ='white',
                        min_font_size=10,
                        stopwords = stopwords).generate(comment_words)

        #plot the WordCloud image                       
        plt.figure(figsize = (8, 8), facecolor = None)
        plt.imshow(wordcloud)
        plt.axis("off")
        plt.tight_layout(pad = 0)

        #save as image  
        plt.savefig(f'static/images/Wordcloud_{datetime.now().date()}_{resp}.png')
        filename = f'static/images/Wordcloud_{datetime.now().date()}_{resp}.png'  
        print(filename) 
        image_name =  f'Wordcloud_{datetime.now().date()}_{resp}.png'
        return render_template('display.html', image_path=filename,image_name = image_name)
    return render_template('wordcloud.html')

@app.route('/uploads/<filename>', methods=['GET', 'POST'])
def download(filename):
    print(filename)
    return send_from_directory('static/images',filename)

#remove entries in database
@app.route('/remove/<id>',methods=['GET','POST'])
def remove_entry(id):
    print(id)
    mydb = connect()
    cur = mydb.cursor()
    sql_query = f'DELETE FROM journal_entries \
    WHERE ID = "{id}"'  
    cur.execute(sql_query)
    mydb.commit()
    flash('Record was successfully deleted')
    return redirect(url_for('show_all'))

#This page will show a page of a single post when clicked on, on the results page
@app.route('/show_post/<entryid>',methods=['POST','GET'])
def show_post(entryid):
    """ Queries sql table for single post and display """
    mydb = connect()
    cur = mydb.cursor()
    sql_query = f'SELECT Entry,Date FROM journal_entries WHERE ID = {entryid}'
    cur.execute(sql_query)
    rows = cur.fetchall()
    
    if request.method == 'POST':
        df = search(cur)
        return render_template('results.html',data = df.values)
    
    return render_template('show_post.html',entry=rows[0])
    
if __name__ == '__main__':
   app.run(port=5000)
