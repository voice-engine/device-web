
from datetime import timedelta
import os
import subprocess
import sys
from urllib.parse import urlparse

from gevent import sleep
from gevent.pywsgi import WSGIServer
from flask import Flask, session, redirect, url_for, escape, request, render_template, jsonify
from notebook import notebookapp
import pam

auth = pam.pam()

app = Flask(__name__)
app.secret_key = os.urandom(16)

# app.permanent_session_lifetime = timedelta(minutes=1)


apps = [
    {'name': 'Music', 'url': 'https://wiki.voicen.io/music', 'icon': 'music.svg'},
    {'name': 'Home Assistant', 'url': 'https://wiki.voicen.io/home_assistant', 'icon': 'home_assistant.svg'},
    {'name': 'Google Assistant', 'url': 'https://wiki.voicen.io/google_assistant', 'icon': 'google_assistant.svg'},
    {'name': 'Amazon Alexa', 'url': 'https://wiki.voicen.io/alexa', 'icon': 'alexa.svg'}
]


@app.route('/')
def index():
    user = session['user'] if 'user' in session else None
    return render_template('index.html', user=user, apps=apps)


@app.route('/terminal')
def terminal():
    o = urlparse(request.url_root)
    url = 'http://{0}:7681/'.format(o.hostname)
    return redirect(url)


def get_jupyter_servers(user):
    home_dir = '/root' if user == 'root' else '/home/{}'.format(user)
    runtime_dir = '{}/.local/share/jupyter/runtime'.format(home_dir)
    
    for _ in range(10):
        servers = list(notebookapp.list_running_servers(runtime_dir))
        if servers:
            return servers
        sleep(0.1)
    
    return servers
    
def jupyter_server_url(server):
    o = urlparse(request.url_root)
    server_url = server['url'].replace('localhost', o.hostname)
    return '{}?token={}'.format(server_url, server['token'])

def run_jupyter_server(user):
    subprocess.Popen(['sudo', '-H', '-u', user, './jupyterlab.sh'])
    # subprocess.Popen(['sudo', '-H', '-u', user, 'jupyter-lab', '-y', '--ip=127.0.0.1', '--no-browser'])

@app.route('/jupyter')
def jupyter():
    if 'user' not in session:
        return redirect(url_for('login', next='jupyter'))
    else:
        user = session['user']
        servers = get_jupyter_servers(user)
        if servers:
            return redirect(jupyter_server_url(servers[0]))
        else:
            run_jupyter_server(user)
            return render_template('jupyter.html')

@app.route('/jupyter/list')
def jupyter_list():
    if 'user' not in session:
        return jsonify([])
    else:
        user = session['user']
        servers = get_jupyter_servers(user)
        return jsonify(servers)


@app.route('/login', methods=['GET', 'POST'])
def login():
    print(request.args)
    print(request.method)
    if request.method == 'POST':
        user = request.form['user']
        password = request.form['password']
        if user == 'root':
            return render_template('login.html',
            message='Not allow root user to login. If you do not have a normal user yet, please go to web terminal and create one')

        if auth.authenticate(user, password):
            session['user'] = request.form['user']
            session.permanent = True
            next = request.args['next'] if 'next' in request.args else 'index'
            return redirect(url_for(next))
        else:
            return render_template('login.html', message='Invalid username or password')

    return render_template('login.html')


@app.route('/logout')
def logout():
    # remove the user from the session if it is there
    session.pop('user', None)
    return redirect(url_for('index'))


port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
print('listening on {}'.format(port))

http_server = WSGIServer(('', port), app)
http_server.serve_forever()
