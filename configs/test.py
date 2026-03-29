import os
basedir = os.path.abspath(os.path.dirname(__file__))

### BASIC APP CONFIG
SALT = '$2b$12$VhFXsbeArj/K4WMB5eEZQO'
SECRET_KEY = 'testing_secret_key_not_for_production_use_a1b2c3d4'
BIND_ADDRESS = '0.0.0.0'
PORT = 9191
HSTS_ENABLED = False

### DATABASE - SQLite
TEST_DB_LOCATION = '/tmp/testing.sqlite'
SQLALCHEMY_DATABASE_URI = 'sqlite:///{0}'.format(TEST_DB_LOCATION)
SQLALCHEMY_TRACK_MODIFICATIONS = False

# SAML Authnetication
SAML_ENABLED = False

# TEST SAMPLE DATA
TEST_USER = 'test'
TEST_USER_PASSWORD = 'test'
TEST_ADMIN_USER = 'admin'
TEST_ADMIN_PASSWORD = 'admin'
TEST_USER_APIKEY = 'wewdsfewrfsfsdf'
TEST_ADMIN_APIKEY = 'nghnbnhtghrtert'