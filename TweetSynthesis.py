import tweepy
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
import openai
import os
import time

# Load API keys securely from environment variables
openai.api_key = os.getenv("OPENAI_API_KEY")
bearer_token = os.getenv("TWITTER_BEARER_TOKEN")

# Function to fetch numeric user IDs from a list of usernames
def get_user_ids(usernames):
    client = tweepy.Client(bearer_token=bearer_token)
    user_ids = {}

    for username in usernames:
        try:
            user = client.get_user(username=username)
            if user.data:
                user_ids[username] = user.data.id
                print(f"User ID for {username}: {user.data.id}")
            else:
                print(f"No data found for username: {username}")
        except Exception as e:
            print(f"Error retrieving user ID for {username}: {e}")
    
    return user_ids

# Function to fetch tweets from multiple accounts using their numeric IDs
def get_twitter_sentiment(user_ids):
    client = tweepy.Client(bearer_token=bearer_token)
    tweets = []

    for username, user_id in user_ids.items():
        try:
            response = client.get_users_tweets(id=user_id, max_results=5) #fetches 5 tweets per user. Free twt api allows pulling 100 posts per month)
            if response.data:
                for tweet in response.data:
                    tweet_url = f"https://twitter.com/i/web/status/{tweet.id}"
                    tweets.append(f"{tweet.text} - {tweet_url}")
            print(f"Fetched tweets for {username}")
        except Exception as e:
            print(f"An error occurred while fetching tweets for {username}: {e}")

        # Add delay to respect rate limits
        time.sleep(900)  # Wait 15 minutes between requests

    return tweets

# Function to save tweets to a file
def save_tweets(tweets):
    filename = "tweets_data.txt"
    with open(filename, "a") as file:  # Open in append mode
        for tweet in tweets:
            file.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {tweet}\n")
    print(f"Saved {len(tweets)} tweets to {filename}")

# Function to fetch and save tweets every 12 hours
def fetch_and_save_tweets():
    print("Fetching tweets...")
    # Cached user IDs (Look to Kaito AI to pick out twitter mindshare and find user IDs)
    user_ids = {
        "aixbt_agent": 1852674305517342720,
        "kwantxbt": 1770955179740782593
    }
    tweets = get_twitter_sentiment(user_ids)
    if tweets:
        save_tweets(tweets)
    else:
        print("No tweets to save.")

# Function to analyze tweets using GPT
def analyze_tweets():
    filename = "tweets_data.txt"
    tweets_all = []

    # Extract all tweets from the file
    try:
        with open(filename, "r") as file:
            for line in file:
                tweets_all.append(line.strip())
    except FileNotFoundError:
        print(f"File {filename} not found. No tweets to analyze.")
        return

    if not tweets_all:
        print("No tweets found in the file. Nothing to analyze.")
        return

    # Prepare the input for GPT
    input_text = "These are the cumulative tweets collected so far:\n\n" + "\n".join(tweets_all)
    input_text += "\n\nWhat are the latest macro takeaways from these tweets?"

    # Send to GPT for analysis
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",  # Use GPT-4 or GPT-3.5
            messages=[
                {"role": "system", "content": "You are an expert in summarizing Twitter data and identifying macro takeaways."},
                {"role": "user", "content": input_text},
            ],
        )
        analysis = response['choices'][0]['message']['content']

        # Save analysis to a file
        analysis_filename = f"tweet_analysis_cumulative_{datetime.now().strftime('%Y-%m-%d')}.txt"
        with open(analysis_filename, "w") as analysis_file:
            analysis_file.write(f"Analysis for cumulative data (as of {datetime.now().strftime('%Y-%m-%d')}):\n\n{analysis}")
        print(f"Analysis saved to {analysis_filename}")
    except Exception as e:
        print(f"Error during GPT analysis: {e}")

# Scheduler to run every 12 hours
def schedule_tweets_fetching():
    scheduler = BlockingScheduler()
    scheduler.add_job(
        fetch_and_save_tweets,
        'interval',
        hours=12,  # Adjusted for Free API rate limits
        max_instances=1,
        misfire_grace_time=300  # Allow a 5-minute delay for missed jobs
    )
    print("Scheduler started for fetching tweets every 12 hours.")
    return scheduler

# Scheduler to analyze tweets once a day
def schedule_analysis():
    scheduler = BlockingScheduler()
    scheduler.add_job(analyze_tweets, 'cron', hour=23, minute=59)  # Run daily at 23:59
    print("Scheduler started for daily analysis.")
    return scheduler

'''
# Main function to manage both schedulers (un-comment once testing complete)
if __name__ == "__main__":
    fetch_scheduler = schedule_tweets_fetching()
    analysis_scheduler = schedule_analysis()

    try:
        # Start both schedulers
        fetch_scheduler.start()
        analysis_scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Schedulers stopped.")
'''

# Uncomment for testing
if __name__ == "__main__":
    # Fetch and save tweets immediately for testing
    print("Running immediate test fetch...")
    fetch_and_save_tweets()

    # Set up the schedulers as usual
    fetch_scheduler = schedule_tweets_fetching()
    analysis_scheduler = schedule_analysis()

    try:
        # Start both schedulers
        fetch_scheduler.start()
        analysis_scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Schedulers stopped.")