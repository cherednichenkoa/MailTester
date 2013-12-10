import cherrypy
import logging
from diagnostics import DiagHandler
import os
import sys
import datetime
import json
import smtplib
import dns.resolver
import dns.exception
import uuid

def CORS():
    cherrypy.response.headers["Access-Control-Allow-Origin"] = '*'
    cherrypy.response.headers["Access-Control-Request-Method"] = 'GET OPTIONS'

cherrypy.tools.CORS = cherrypy.Tool('before_finalize', CORS)

class root:
    diag = DiagHandler()

    @cherrypy.expose
    def check_email(self, *args, **kwargs):
        email = args[0]
        username, domain = email.split('@')
        result = {'code':0, 'message': 'Unknown Exception'}
        mail_servers = []

        try:
            mail_servers = sorted([x for x in dns.resolver.query(domain, 'MX')], key=lambda k: k.preference)
        except dns.exception.Timeout as ex:
            result = {'code':5, 'message': 'DNS Timeout'}
        except dns.resolver.NXDOMAIN as ex:
            result = {'code':4, 'message': 'Mail server not found for domain'}
        except Exception as ex:
            result = {'code':0, 'message': 'Unknown Exception: ' + ex.message}

        for mail_server in mail_servers:
            if result['code'] != 0:
                break
            server = smtplib.SMTP(str(mail_server.exchange)[:-1])
            (code, msg) = server.helo('MailTester')
            (code, msg) = server.docmd('MAIL FROM:', '<mailtester@gmail.com>')
            if 200 <= code <= 299:
                (code, msg) = server.docmd('RCPT TO:', '<{}>'.format(email))
                if 500 <= code:
                    result = {'code':3, 'message': 'Mail server found for domain, but the email address is not valid'}
                else:
                    (code_bad_email, msg) = server.docmd('RCPT TO:', '<{}@{}>'.format(str(uuid.uuid4()), domain))
                    if code != code_bad_email and 200 <= code <= 299:
                        result = {'code':1, 'message': 'Mail server indicates this is a valid email address'}
                    else:
                        result = {'code':2, 'message': 'Mail server found for domain, but cannot validate the email address'}

        resp = json.dumps(result)
        if 'callback' in kwargs:
            resp = '%s(%s)' % (kwargs['callback'], resp)
            cherrypy.response.headers['Content-Type']= 'application/javascript'

        return resp

if __name__ == "__main__":

    server_host = '0.0.0.0'
    server_port = int(sys.argv[1]) if len(sys.argv) > 1 else 9090
    current_dir = os.path.dirname(os.path.abspath(__file__))
    cherrypy.config.update({
        'server.socket_host' : server_host,
        'server.socket_port' : server_port,
        'tools.CORS.on' : True
    })
    cherrypy.process_start_time = datetime.datetime.now()

    root = root()

    if len(sys.argv) > 2 and sys.argv[2] == 'dev':
        logging.info('Starting web server with QuickStart')
        cherrypy.quickstart(root=root)
    else:
        logging.info('Starting web server')
        cherrypy.engine.autoreload.unsubscribe()
        cherrypy.tree.mount(root)
        cherrypy.engine.start()
        cherrypy.engine.block()