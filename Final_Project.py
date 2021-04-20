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

import secrets as secrets # file that contains your OAuth credentials


CACHE_FILENAME = "cache.json"
CACHE_DICT = {}


client_key = secrets.TWITTER_API_KEY
client_secret = secrets.TWITTER_API_SECRET
access_token = secrets.TWITTER_ACCESS_TOKEN
access_token_secret = secrets.TWITTER_ACCESS_TOKEN_SECRET

oauth = OAuth1(client_key,
            client_secret=client_secret,
            resource_owner_key=access_token,
            resource_owner_secret=access_token_secret)

Alpha_API = secrets.ALPHA_API_KEY

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
    paragraphs = soup.find_all('p', class_="Paragraph-paragraph-2Bgue ArticleBody-para-TD_9x")

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
            sentiment_score = sentiment(article(v), positive_list, negative_list)
            dict_news[k] = (v, sentiment_score[0])
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
        CACHE_DICT[key] = make_request(baseurl, params, oauth=None)
        return CACHE_DICT[key]


if __name__ == "__main__":

    CACHE_DICT = open_cache()

    # word list
    # path = 'https://drive.google.com/uc?export=download&code=15UPaF2xJLSVz8DYuphierz67trCxFLcl'
    path = "./LoughranMcDonald_SentimentWordLists_2018.xlsx"
    df = pd.read_excel(path, sheet_name='Negative', header=None)
    negative_list = list(df.to_numpy().flatten())
    df = pd.read_excel(path, sheet_name='Positive', header=None)
    positive_list = list(df.to_numpy().flatten())

    # Twitter
    current_time = datetime.datetime.now(timezone('US/Eastern'))
    twitter_df = pd.DataFrame(columns=['Code', 'Date', 'Sentiment_Score'])
    for code in ['AAPL', 'MSFT', 'AMZN']:
        sentiment_scores, date_list = weekly_sentiment_tweets(code, current_time, positive_list, negative_list)
        for i in range(7):
            df = pd.DataFrame({'Code': code, 'Date': date_list[i], 'Sentiment_Score': sentiment_scores[i]}, index=[0])
            twitter_df = twitter_df.append(df, ignore_index=True)
    

    # news
    newslist_df = pd.DataFrame(columns=['Code', 'Headline', 'URL', 'Sentiment_Score'])
    for code in ['AAPL', 'MSFT', 'AMZN']:
        news_dict = news_list_with_sentiment(code, positive_list, negative_list)
        for k, v in news_dict.items():
            df = pd.DataFrame({'Code': code, 'Headline': k, 'URL':v[0], 'Sentiment_Score': v[1]}, index=[0])
            newslist_df = newslist_df.append(df, ignore_index=True)

    # Alpha Vantage 
    stockprice_df = pd.DataFrame(columns=['Code', 'Date', 'Stock_Price'])
    for code in ['AAPL', 'MSFT', 'AMZN']:
        stcok_dict = get_alpha(code, "TIME_SERIES_DAILY")['Time Series (Daily)']
        for k, v in stcok_dict.items():
            df = pd.DataFrame({'Code': code, 'Date': k, 'Stock_Price': v['4. close']}, index=[0])
            stockprice_df = stockprice_df.append(df, ignore_index=True)

    time.sleep(60) # Avoid access limit (5 calls per minute)

    overview_df = pd.DataFrame(columns=['Code', 'Name', 'Industry', 'Address'])
    for code in ['AAPL', 'MSFT', 'AMZN']:
        overview_dict = get_alpha(code, "OVERVIEW")
        df = pd.DataFrame({'Code': code, 'Name': overview_dict['Name'],
         'Industry': overview_dict['Industry'], "Address": overview_dict['Address']}, index=[0])
        overview_df = overview_df.append(df, ignore_index=True)
        

    save_cache(CACHE_DICT)


    # Create a database
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
                            Sentiment_Score REAL NOT NULL)
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

    twitter_df.to_sql('twitter', conn, if_exists='append')
    newslist_df.to_sql('newslist', conn, if_exists='append')
    stockprice_df.to_sql('stockprice', conn, if_exists='append')
    overview_df.to_sql('overview', conn, if_exists='append', index=False)

    cur.close()
    conn.close()

    
