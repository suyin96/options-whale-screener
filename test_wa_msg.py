import os
from twilio.rest import Client

def test():
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    my_number = os.getenv('MY_PHONE_NUMBER')
    
    client = Client(account_sid, auth_token)
    try:
        message = client.messages.create(
            from_='whatsapp:+14155238886',
            body="✅ Test from GitHub Actions!",
            to=my_number
        )
        print(f"Sent! SID: {message.sid}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
