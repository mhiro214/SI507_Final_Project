#########################################
##### Name: Hiroyuki Makino         #####
##### Uniqname: mhiro               #####
#########################################

from requests_oauthlib import OAuth1
import json
import requests
import pandas as pd
from bs4 import BeautifulSoup
import re
import datetime
from pytz import timezone
import sqlite3
import time
from flask import Flask, render_template, request
import plotly.graph_objs as go
import plotly.express as px
from plotly.subplots import make_subplots

import secrets as secrets # file that contains your OAuth credentials


CACHE_FILENAME = "cache.json"


client_key = secrets.TWITTER_API_KEY
client_secret = secrets.TWITTER_API_SECRET
access_token = secrets.TWITTER_ACCESS_TOKEN
access_token_secret = secrets.TWITTER_ACCESS_TOKEN_SECRET

oauth = OAuth1(client_key,
            client_secret=client_secret,
            resource_owner_key=access_token,
            resource_owner_secret=access_token_secret)

Alpha_API = secrets.ALPHA_API_KEY


#################### [START] Helper functions ####################

def open_cache():
    ''' Opens the cache file if it exists and loads the JSON into
    the CACHE_DICT dictionary.
    if the cache file doesn't exist, creates a new cache dictionary
    
    Parameters
    ----------
    None
    
    Returns
    -------
    The opened cache: dict
    '''
    try:
        cache_file = open(CACHE_FILENAME, 'r')
        cache_contents = cache_file.read()
        cache_dict = json.loads(cache_contents)
        cache_file.close()
    except:
        cache_dict = {}
    return cache_dict


def save_cache(cache_dict):
    ''' Saves the current state of the cache to disk
    
    Parameters
    ----------
    cache_dict: dict
        The dictionary to save
    
    Returns
    -------
    None
    '''
    dumped_json_cache = json.dumps(cache_dict)
    fw = open(CACHE_FILENAME,"w")
    fw.write(dumped_json_cache)
    fw.close() 


def make_request(baseurl, params, oauth):
    '''Make a request to the Web API using the baseurl and params
    
    Parameters
    ----------
    baseurl: string
        The URL for the API endpoint
    params: dictionary
        A dictionary of param:value pairs
    
    Returns
    -------
    dict
        the data returned from making the request in the form of 
        a dictionary
    '''
    #TODO Implement function
    if oauth == None:
        response = requests.get(baseurl, params=params)
    else:
        response = requests.get(baseurl, params=params, auth=oauth)
    ret = json.loads(response.text)
    return ret


def get_tweets(code, since, until):
    '''Get tweets related to a company
    
    Parameters
    ----------
    code: string
        Company code (e.g., AAPL)
    
    Returns
    -------
    list
        list of tweets that include the hashtag of inputted company (e.g., #AAPL)
    '''

    baseurl = "https://api.twitter.com/1.1/search/tweets.json"
    count = 100
    params = {'q': code, 'count': count, "tweet_mode": "extended",
     "lang": "en", "since": since, "until": until}

    key = code + "_" + since + "_" + until
    if key in CACHE_DICT.keys():
        print('fetching cached data')
        return CACHE_DICT[key]
    
    else:
        print("making new request")
        list_tweet_text = list()
        tweet_data = make_request(baseurl, params, oauth)
        if "errors" in tweet_data.keys():
            return []
        else:
            list_tweets = tweet_data['statuses']
            for tweet in list_tweets:
                list_tweet_text.append(tweet['full_text'].replace("\n", " "))
            CACHE_DICT[key] = list_tweet_text        
            return list_tweet_text


def sentiment(list_sentences, positive_list, negative_list):
    '''Calculate a sentiment score of tweets
    
    Parameters
    ----------
    list_sentences: list
        list of sentences
    
    Returns
    -------
    float
        sentiment score
    '''
    list_words = " ".join(list_sentences).split()
    pos = 0
    neg = 0
    for word in list_words:
        word = re.sub(r"[^a-zA-Z]", "", word)
        if word.upper() in positive_list:
            pos += 1
        if word.upper() in negative_list:
            neg += 1
    
    if pos + neg == 0:
        score = 0
    else:
        score = (pos - neg) / (pos + neg)
    return score, pos, neg


def weekly_sentiment_tweets(code, current_time, positive_list, negative_list):
    '''Calculate a sentiment score of tweets
    
    Parameters
    ----------
    code: str
        company code (e.g., AAPL)
    current_time: datetime.datetime
        current time
    positive_list, negative_list: list
        Loughran McDonald Sentiment Word Lists

    Returns
    -------
    list
        sentiment scores of last 7 days
    '''
    date_list = list()
    sentiment_scores = list()

    for i in range(7):
        time = current_time + datetime.timedelta(days=-(i+1))
        date = time.strftime('%Y-%m-%d')
        since = date + "_00:00:00_EST"
        until = date + "_23:59:59_EST"
        list_tweets = get_tweets(code, since, until)
        sentiment_scores.append(sentiment(list_tweets, positive_list, negative_list)[0])
        date_list.append(date)

    return sentiment_scores, date_list


def news_list(code):
    '''Create a news list from Reuters
    
    Parameters
    ----------
    code: str
        company code (e.g., AAPL)

    Returns
    -------
    dict
        keys: headline, values: URL
    '''

    url = "https://www.reuters.com/companies/" + code + ".O"
    html = requests.get(url)
    html_text = html.text
    soup = BeautifulSoup(html_text, 'html.parser')
    news_section = soup.find_all('div', class_="Profile-news-3puYH Profile-section-1sted")[0]
    list_links = news_section.find_all('a')

    dict_news = dict()
    for link in list_links:
        href = link.get('href')
        name = link.get_text()
        dict_news[name] = href
    return dict_news


def article(url):
    '''Obtain text of an article
    
    Parameters
    ----------
    url: str
        url of an article

    Returns
    -------
    list
        a list of paragraphs of an article
    '''

    html = requests.get(url)
    html_text = html.text
    soup = BeautifulSoup(html_text, 'html.parser')
    paragraphs = soup.find_all('div', class_="ArticleBody__container___D-h4BJ")
    if paragraphs == []:
        paragraphs = soup.find_all('div', class_="ArticleBodyWrapper")

    list_paragraphs = list()

    for para in paragraphs:
        list_paragraphs.append(para.get_text())
    return list_paragraphs

def news_list_with_sentiment(code, positive_list, negative_list):
    '''Calculate sentiment scores for each article
    Create a news list with sentiment scores
    
    Parameters
    ----------
    code: str
        company code (e.g., AAPL)
    positive_list, negative_list: list
        Loughran McDonald Sentiment Word Lists

    Returns
    -------
    dict
        keys: headline, values: (URL, sentiment score)
    '''
    key = code + "_newslist"
    if key in CACHE_DICT.keys():
        print('fetching cached data')
        return CACHE_DICT[key]
    
    else:
        print("making new request")
        dict_news = news_list(code)
        for k, v in dict_news.items():
            text = article(v)
            sentiment_score = sentiment(text, positive_list, negative_list)
            dict_news[k] = (v, sentiment_score[0], text)
        CACHE_DICT[key] = dict_news
        return dict_news

def get_alpha(code, function):
    '''Get strock prices or company information using Alpha Vantage API
    
    Parameters
    ----------
    code: string
        Company code (e.g., AAPL)
    funtion: string
        "TIME_SERIES_DAILY": stock prices
        "OVERVIEW": Company information (Name, Address, Industry, etc)
    
    Returns
    -------
    dict
        a dictionary of stock prices or company information
    '''

    baseurl = 'https://www.alphavantage.co/query'
    params = {'function': function, "symbol": code, "apikey": Alpha_API}
 
    key = code + "_" + function
    if key in CACHE_DICT.keys():
        print('fetching cached data')
        return CACHE_DICT[key]
    
    else:
        print('making new request')
        stock_dict = make_request(baseurl, params, oauth=None)
        if 'Note' not in stock_dict.keys():
            CACHE_DICT[key] = stock_dict
        return stock_dict

def get_df(code, source):
    '''Make a dataframe 
    
    Parameters
    ----------
    code: string
        Company code (e.g., AAPL)
    source: string
        Data source (twitter, news, stockprice or overview)
    
    Returns
    -------
    DataFrame
        twitter -> columns=['Code', 'Date', 'Sentiment_Score']
        news ->  columns=['Code', 'Headline', 'URL', 'Sentiment_Score', 'Text']
        stockprice -> columns=['Code', 'Date', 'Stock_Price']
        overview -> columns=['Code', 'Name', 'Industry', 'Address']
    '''

    if source == "twitter":
        current_time = datetime.datetime.now(timezone('US/Eastern'))
        df_twitter = pd.DataFrame(columns=['Code', 'Date', 'Sentiment_Score'])
        sentiment_scores, date_list = weekly_sentiment_tweets(code, current_time, positive_list, negative_list)
        for i in range(7):
            df = pd.DataFrame({'Code': code, 'Date': date_list[i], 'Sentiment_Score': sentiment_scores[i]}, index=[0])
            df_twitter = df_twitter.append(df, ignore_index=True)
        return df_twitter

    elif source == "stockprice":
        df_stockprice = pd.DataFrame(columns=['Code', 'Date', 'Stock_Price'])
        stock_dict = get_alpha(code, "TIME_SERIES_DAILY")

        if 'Note' in stock_dict.keys():
            return df_stockprice
        else:
            stock_dict = stock_dict['Time Series (Daily)']
            for k, v in stock_dict.items():
                df = pd.DataFrame({'Code': code, 'Date': k, 'Stock_Price': float(v['4. close'])}, index=[0])
                df_stockprice = df_stockprice.append(df, ignore_index=True)
            return df_stockprice

    elif source == "overview":
        overview_dict = get_alpha(code, "OVERVIEW")
        if 'Note' in overview_dict.keys():
            df_stockprice = pd.DataFrame(columns=['Code', 'Name', 'Industry', 'Address'])            
            return df_stockprice
        else:
            df_overview = pd.DataFrame({'Code': code, 'Name': overview_dict['Name'],
            'Industry': overview_dict['Industry'], "Address": overview_dict['Address']}, index=[0])
            return df_overview

    elif source == "news":
        df_newslist = pd.DataFrame(columns=['Code', 'Headline', 'URL', 'Sentiment_Score', 'Text'])
        news_dict = news_list_with_sentiment(code, positive_list, negative_list)
        for k, v in news_dict.items():
            if v[2] != []:
                df = pd.DataFrame({'Code': code, 'Headline': k, 'URL':v[0], 'Sentiment_Score': v[1], "Text": v[2]}, index=[0])
                df_newslist = df_newslist.append(df, ignore_index=True)
        return df_newslist

def plot_twitter(df_twitter):
    ''' Make a bar graph of twitter sentiment scores

    Parameters
    ----------
    df_twitter: DataFrame
        columns=['Code', 'Date', 'Sentiment_Score']
    
    Returns
    -------
    fig

    '''
    x_vals = df_twitter['Date']
    y_vals = df_twitter['Sentiment_Score']

    data = go.Bar(x=x_vals, y=y_vals)
    return data

def plot_stockprice(df_stockprice):
    ''' Make a line chart of stock prices

    Parameters
    ----------
    df_stockprice: DataFrame
        columns=['Code', 'Date', 'Stock_Price']
    
    Returns
    -------
    fig
    '''
    x_vals = df_stockprice['Date']
    y_vals = df_stockprice['Stock_Price']
    data = go.Scatter(x=x_vals, y=y_vals, mode='lines')
    return data

def create_database(df_overview, df_stockprice, df_twitter, df_newslist):
    ''' Create a database from DataFrames 

    Parameters
    ----------
    df_overview: DataFrame
        columns=['Code', 'Name', 'Industry', 'Address']
    df_stockprice: DataFrame
        columns=['Code', 'Date', 'Stock_Price']
    df_twitter: DataFrame
        columns=['Code', 'Date', 'Sentiment_Score']
    df_newslist: DataFrame
        columns=['Code', 'Headline', 'URL', 'Sentiment_Score', 'Text']
    
    Returns
    -------
    None
    '''
    dbname = 'Database.sqlite'
    conn = sqlite3.connect(dbname)
    cur = conn.cursor()

    cur.execute('DROP table IF EXISTS twitter')
    cur.execute('DROP table IF EXISTS newslist')
    cur.execute('DROP table IF EXISTS stockprice')
    cur.execute('DROP table IF EXISTS overview')

    sql = """
        CREATE TABLE twitter("index" INTEGER PRIMARY KEY AUTOINCREMENT,
                            Code TEXT "FOREIGN KEY",
                            Date TEXT NOT NULL,
                            Sentiment_Score REAL NOT NULL)
    """
    cur.execute(sql)

    sql = """
        CREATE TABLE newslist("index" INTEGER PRIMARY KEY AUTOINCREMENT,
                            Code TEXT "FOREIGN KEY",
                            Headline TEXT NOT NULL,
                            URL TEXT NOT NULL,
                            Sentiment_Score REAL NOT NULL,
                            'Text' TEXT NOT NULL)
    """
    cur.execute(sql)

    sql = """
        CREATE TABLE stockprice("index" INTEGER PRIMARY KEY AUTOINCREMENT,
                            Code TEXT "FOREIGN KEY",
                            Date TEXT NOT NULL,
                            Stock_Price REAL NOT NULL)
    """
    cur.execute(sql)

    sql = """
        CREATE TABLE overview(Code TEXT "PRIMARY KEY",
                            Name TEXT NOT NULL,
                            Industry TEXT NOT NULL,
                            Address TEXT NOT NULL)
    """
    cur.execute(sql)

    df_twitter.to_sql('twitter', conn, if_exists='append')
    df_newslist.to_sql('newslist', conn, if_exists='append')
    df_stockprice.to_sql('stockprice', conn, if_exists='append')
    df_overview.to_sql('overview', conn, if_exists='append', index=False)

    cur.close()
    conn.close()



#################### [END] Helper functions ####################

# word list
# path = 'https://drive.google.com/uc?export=download&code=15UPaF2xJLSVz8DYuphierz67trCxFLcl'
path = "./LoughranMcDonald_SentimentWordLists_2018.xlsx"
df = pd.read_excel(path, sheet_name='Negative', header=None)
negative_list = list(df.to_numpy().flatten())
df = pd.read_excel(path, sheet_name='Positive', header=None)
positive_list = list(df.to_numpy().flatten())

# Flask
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/results', methods=['POST'])
def results():

    Code = request.form['Code']

    # Create DataFrames
    # Alpha Vantage (Overview & Stock Price)
    df_overview = get_df(Code, 'overview')
    df_stockprice = get_df(Code, 'stockprice')
    # Twitter
    df_twitter = get_df(Code, 'twitter')
    # News
    df_newslist = get_df(Code, "news")

    if len(df_overview) == 0 or len(df_stockprice) == 0:
        list_overview = ["Alpha limit"]
        div = ""
        list_newslist = []
        len_newslist = 0
    
    elif any(list(df_twitter['Sentiment_Score'])) == False:
        list_overview = ["Twitter limit"]
        div = ""
        list_newslist = []
        len_newslist = 0

    else:
        list_overview = [df_overview.iloc[0,0], df_overview.iloc[0,1], df_overview.iloc[0,2], df_overview.iloc[0,3]]
        data_stock = plot_stockprice(df_stockprice)
        data_twitter = plot_twitter(df_twitter)

        # Create graphs
        fig = make_subplots(rows=1, cols=2, subplot_titles=("Stock Price", "Twitter Sentiment Score"))
        fig.add_trace(data_stock, row=1, col=1)
        fig.add_trace(data_twitter, row=1, col=2)
        fig.update_layout(showlegend=False)
        fig.update_yaxes(range=[-1, 1], row=1, col=2)
        div = fig.to_html(full_html=False)

        list_newslist = [df_newslist['Headline'].values.tolist(), df_newslist['URL'].values.tolist(), 
        df_newslist['Sentiment_Score'].values.tolist()]
        len_newslist = len(list_newslist[0])

    create_database(df_overview, df_stockprice, df_twitter, df_newslist)
    save_cache(CACHE_DICT)

    return render_template('results.html', Code=Code, list_overview=list_overview,
     div = div, list_newslist = list_newslist, len_newslist=len_newslist)

if __name__ == "__main__":
    CACHE_DICT = open_cache()
    app.run(debug=True)

 

