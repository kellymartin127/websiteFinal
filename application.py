import os
import requests
import flask
from flask import Flask, render_template, session, request, redirect, url_for
from flask_socketio import SocketIO, send, emit, join_room, leave_room
import pickle
from collections import deque

#Setting up FLask and Socket.io
app = Flask(__name__)
app.secret_key = "hello"
socketio = SocketIO(app)

#Setting up the useful global variables
Channels = []
PrivateChannels = []
Users = []
channelsPasswords = dict()
channelsMessages = dict()

# Creating a default Channel
Channels.append("Channel 1")
channelsMessages["Channel 1"] = deque()

#Home route
@app.route("/")
def home():
    if "user" in session:
        return render_template("index.html")
    else:
        return render_template("login.html")
#Log in route 
@app.route("/login", methods=["POST", "GET"])
def login():
    if request.method == "POST":
        session.permanent = True
        user = request.form.get("username")
        #If the username is already in use, show an error.
        if user in Users:
            return render_template("login.html", message="A user with that username is already logged in :(")
        #Otherwise it logs the user.
        session["user"] = user
        Users.append(user)
        pickle.dump(user, open( "save.p", "wb" ))
        return redirect(url_for("user"))
    else:
        if "user" in session:
            return redirect(url_for("user"))
        return render_template("login.html")

#Redirect route
@app.route("/user")
def user():
    if "user" in session:
        return redirect(url_for("home"))
    else:
        return redirect(url_for("login"))
#Log out route
@app.route("/logout")
def logout():
    #If it is logged, then it logs the user out
    if "user" in session:
        user = session["user"]
        if user in Users:
            Users.remove(user)
            session.pop("user", None)
            return redirect(url_for("login"))
        else:
            session.pop("user", None)
            return redirect(url_for("login"))
    #Otherwise...
    else:
            return render_template("login.html", message="You cannot get rid of something that you don't have :/")

#List of channel route
@app.route("/channels", methods={"GET"})
def channels_view():
    if "user" in session:
       user = session["user"]
       return render_template("channels.html", channels=Channels, user=user, secretChannels = PrivateChannels)
    return render_template("login.html", message="You are not logged in :(")

#Create channel route
@app.route("/shhh/<channel>", methods= ['GET','POST'])
def secret(channel):
    if request.method == "GET":
        return render_template("top_secret.html", channel=channel)
    #If the user inserted a password...
    if request.form.get("password"):
        #Compares the input with the real password.
        realPassword = channelsPasswords[channel].pop()
        channelsPasswords[channel].append(realPassword)
        #If both are equal...
        if request.form.get("password") == realPassword:
            #Then it redirects to the channel
            return redirect("/channels/" + channel)
        #Otherwise, it prompts wrong password.
        return render_template("top_secret.html", channel=channel, message= "Wrong password")
    #If the the user didn't type anything, then it prompts an error message.
    return render_template("top_secret.html", channel=channel, message= "Insert a password")
            
    
#Create new channel route
@app.route("/create", methods=['GET','POST'])
def create():
    """ Create a channel and redirect to its page """
    if session.get("user"):
        if request.form.get("channel"):
            newChannel = request.form.get("channel")
            if request.method == "POST":
                #If ocassionally the user enter an empty channel name, then the website prompts an error message.
                if newChannel == '':
                    return render_template("create_channel.html", channels = Channels, secretChannels = PrivateChannels, message="You cannot create channel with an empty name.")
                #If it tries to create a channel with a name already taken, then the website prompts an error message.
                if newChannel in Channels:
                    return render_template("create_channel.html", channels = Channels, secretChannels = PrivateChannels, message="I won't allow you to overwrite a channel! Think another name.")
                
                Channels.append(newChannel)
                channelsMessages[newChannel] = deque()
                return redirect("/channels/" + newChannel)
            
            else:
                return render_template("create_channel.html", channels = Channels, secretChannels = PrivateChannels)
        
        #Create secret channel part
        else:
            if request.form.get("secretChannel"):
                secretChannel = request.form.get("secretChannel")
                if request.form.get("password"):
                    password = request.form.get("password")
                    if request.method == "POST":
    
                        if secretChannel == '':
                            return render_template("create_channel.html", channels = Channels, secretChannels = PrivateChannels, message="You cannot create channel with an empty name.")
                        
                        if secretChannel in Channels:
                            return render_template("create_channel.html", channels = Channels, secretChannels = PrivateChannels, message="It seems that someone has the same secret :$. Think another name for the channel.")

                        if secretChannel in PrivateChannels:
                            return render_template("create_channel.html", channels = Channels, secretChannels = PrivateChannels, message="It seems that someone has the same secret :$. Think another name for the channel.")
                        
                        
                        PrivateChannels.append(secretChannel)
                        channelsMessages[secretChannel] = deque()
                        #Creating a dictionry for the Channel password and saving it.
                        channelsPasswords[secretChannel] = deque()
                        channelsPasswords[secretChannel].append(password)
                        return redirect("/channels/" + secretChannel)
                    
                    return render_template("create_channel.html", channels = Channels, secretChannels = PrivateChannels)
               
                return render_template("create_channel.html", channels = Channels, secretChannels = PrivateChannels, message = "You have to insert a password for your secret. Don't forget it!")
            
            return render_template("create_channel.html", channels = Channels, secretChannels = PrivateChannels)
    
    else:  
        return render_template("login.html", message= "You cannot create a channel if you haven't logged in first")

#Channel chat route
@app.route("/channels/<channel>", methods=['GET','POST'])
def enter_channel(channel):
    if "user" in session:
        user = session["user"]
        session['current_channel'] = channel
        if request.method == "POST":
            
            return redirect("/")
        else:
            return render_template("channel.html", channel=channel, user=user, messages=channelsMessages[channel])
    else:
        return render_template("login.html", message="You have not logged in")

#Emit message functionality
@socketio.on("emit message")
def emitMessage(message, timestamp):
    
    room = session.get('current_channel')
    user = session.get("user")
    
    if len(channelsMessages[room]) > 100:
        channelsMessages[room].popleft()
    
    string = '<' + timestamp + '> - ' + '[' + user + ']:  ' + message
    channelsMessages[room].append(string)
    
    emit("announce message", {"user": user,"timestamp": timestamp, "message": message}, room=room, broadcast=True)

#Emit left functionality
@socketio.on("left", namespace='/')
def left():
    """ Send message to announce that user has left the channel """

    room = session.get('current_channel')

    leave_room(room)

    emit('state', {
        'message': "<" + session.get('user') + " has left the channel>"}, 
        room=room)    

#Emit connect functionality
@socketio.on ("connected", namespace='/')
def joined():

    room = session.get('current_channel')
    
    join_room(room)
    
    emit('state', {
        'message': "<" + session.get("user") + " has joined the channel>",
        'user': session.get("user"),
        'channel': room},
        room = room)

if __name__ == "__main__":
	app.run(debug=True)
 
 