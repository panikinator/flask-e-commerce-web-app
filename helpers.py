#some helper functions are defined here

#import the libraries
from functools import wraps
from flask import redirect, session, flash
from models import Admin, Customer, Product, Reward, Supplier
from datetime import datetime
from collections import defaultdict

DEFAULT_ADMIN_PASSWORD = "supersecretpassword"
DEFAULT_ADMIN_EMAIL = "admin@example.com"

# a decorator function for routes that require the user to login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("customer_uuid") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

# a decorator function for routes that require admin priviledges
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("admin_uuid") is None:
            flash("You need to login first", category="info")
            return redirect("/admin/login")
        return f(*args, **kwargs)
    return decorated_function

# function for default dicts
def return_0():
    return 0

# function to generate keys for time series data
def generate_time_for_timeseries():
    return str(datetime.now().replace(minute=0, second= 0, microsecond=0))

# function to check file type
def allowed_file(filename, ALLOWED_EXTENSIONS):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# function for initial shelve db setup
def first_time_shelve_setup(shelf):
    shelf["issetup"] = True
    shelf["customers"] = {}
    shelf["products"] = {}
    shelf["admins"] = {}
    shelf["rewards"] = {}
    shelf["suppliers"] = {}
    shelf["account_creation_history"] = defaultdict(return_0)
    shelf["orders_history"] = defaultdict(return_0)
    shelf["activity_history"] = defaultdict(return_0)

    # a few dummy classes
    admin = Admin("admin", DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD)
    shelf["admins"][admin.uuid] = admin

    test_customer = Customer("Default User", "default@example.com", "101000100", "notsafe", "Earth")
    shelf["customers"][test_customer.uuid] = test_customer

    test_supplier = Supplier("Default company", "Earth", "http://default.com", "100001000", "default@default.com")

    test_reward = Reward("Everyone's Reward", 10, 20, 5)
    shelf["rewards"][test_reward.uuid] = test_reward

    test_product1 = Product("CardBoard Box", "The best box out there", "Box inc.", 1000, "/static/uploads/cardboard_box.jpg", 10.0, 6.0, test_supplier.uuid)
    test_product2 = Product("Cup", "The best cup out there", "Cup inc.", 100, "/static/uploads/cup.jpg", 4.0, 2.0, test_supplier.uuid)
    test_product3 = Product("Jar", "The best jar out there", "Jar inc.", 70, "/static/uploads/jar.jpg", 30.0, 25.0, test_supplier.uuid)
    test_product4 = Product("Pots", "The best Pots out there", "Pots inc.", 940, "/static/uploads/pot.jpg", 100.0, 60.0, test_supplier.uuid)
    test_product5 = Product("The Shoes", "The best shoes out there", "The Shoe Company", 50, "/static/uploads/shoe.jpg", 100.0, 60.0, test_supplier.uuid)

    shelf["suppliers"][test_supplier.uuid] = test_supplier
    shelf["products"][test_product1.uuid] = test_product1
    shelf["products"][test_product2.uuid] = test_product2
    shelf["products"][test_product3.uuid] = test_product3
    shelf["products"][test_product4.uuid] = test_product4
    shelf["products"][test_product5.uuid] = test_product5


    shelf.sync()

