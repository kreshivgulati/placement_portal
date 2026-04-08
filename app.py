import os
from flask import Flask
def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=os.path.join(app.instance_path, 'flaskr.sqlite'),
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)
    import database as db
    db.init_app(app)
    from blueprints.auth import auth_bp
    app.register_blueprint(auth_bp)
    from blueprints.student import student_bp
    app.register_blueprint(student_bp)
    from blueprints.company import company_bp
    app.register_blueprint(company_bp)
    from blueprints.admin import admin_bp
    app.register_blueprint(admin_bp)
    
    return app
