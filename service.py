from flask import Flask, request
from flask_restful import Resource, Api
import json
import sys
import imp
import os
import subprocess

services = {}

app = Flask(__name__)
api = Api(app)

class GenericService(Resource):
    def post(self):
        rule = str(request.url_rule)
        if rule in services.keys():
            service = services[rule]    
            params = service['request']['params']
            param_values = {}           
            for param_key in params:
                param = params[param_key]
                if param['type'] == 'file':
                    if request.files:
                        file = request.files['file']
                        filename = os.path.join('/tmp', file.filename)
                        file.save(filename)
                        file.close()
                        param_values[param_key] = filename
                else:
                    param_values[param_key] = request.args.get(param_key)
                    
            command = service['command'].format(**param_values)
            try:
                command_output = subprocess.check_output(command.split(' ')).decode()
                obj = json.loads(command_output)
            except ValueError:
                return {'msg': 'Service Error: %s' %command_output}
            except subprocess.CalledProcessError:
                return {'msg': 'Service Error'}
            response = {}
            for param_key in service['response']['params']:
                if param_key in obj:
                    response[param_key] = obj[param_key]
            return response
        else:
            return {'msg': "Invalid Service"}
        
        
def run():
    routes = []
    config = None
    with open('./config.json', 'r') as config_fp:
        config = json.loads(config_fp.read())
    
    for service_path in config[u'service_paths']:    
        with open(service_path + '/manifest.json', 'r') as service_config_file:
            service_config = json.load(service_config_file)
            for service in service_config:
                if service['type'] == 'python':
                    # Import the module and run it a flask class
                    sys.path.insert(0, service_path)
                    path = os.path.join(service_path, service['file'])
                    mod_name,file_ext = os.path.splitext(path[-1])
                    mod = imp.load_source(mod_name, path)
                    cls = getattr(mod, service['class'])
                    prep = getattr(mod, service['prepare'])
                    api.add_resource(cls, service['route'])
                    prep()
                elif service['type'] == 'command':
                    services[service['route']] = service
                    #api.add_resource(GenericService, service['route'])
                    routes.append(service['route'])
    
    if len(routes):
        api.add_resource(GenericService, *routes)
    
    
    app.run(config['bind'], config['port'], debug=True)    
        
    
if __name__ == '__main__':
    run()
    # load_all()
    # app.run('0.0.0.0', debug=True)
