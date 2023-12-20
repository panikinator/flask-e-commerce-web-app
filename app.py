# The main python/flask web app file

# Importing all the required libraries

# flask related imports
from flask import Flask, session, render_template, flash, request, redirect, abort
from markupsafe import Markup
from flask_session import Session
from werkzeug.utils import secure_filename
# standard python modules
import shelve
from tempfile import TemporaryDirectory
import dataclasses
import os
import random
from uuid import uuid4
# imports from custom code
from helpers import first_time_shelve_setup, login_required, admin_only, allowed_file, generate_time_for_timeseries
from models import CartItem, Product, Reward, RewardStatus, Supplier, Customer, Order, OrderStatus

# library for data visualization
import plotly.express as px

# initializing shelve db
shelf = shelve.open("./shelve/shelvefile", writeback=True)
if not shelf.get("issetup"):
    first_time_shelve_setup(shelf)

# initializing flask app and config
app = Flask(__name__)

app.config["SESSION_PERMANENT"] = True
app.config["SESSION_TYPE"] = "filesystem"
app.config["SECRET_KEY"] = "asodboabsdjkabsjkdbajksbdakjsbd "
app.config['UPLOAD_FOLDER'] = 'static/uploads/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# using session to remember user logins
Session(app)

# before every request activity is logged for data collection
@app.before_request
def before_request():
    shelf["activity_history"][generate_time_for_timeseries()] += 1
    shelf.sync()
    print(generate_time_for_timeseries(), shelf["activity_history"][generate_time_for_timeseries()])
    print(shelf["activity_history"])

# The user side-
# the main index route
# login_required decorator makes sure the user is logged n first
@app.route("/")
@login_required
def index():
    all_products = shelf["products"]

    products = random.sample(list(all_products.values()), 3)
    customer = shelf["customers"][session.get("customer_uuid")]
    products_in_cart = list(map(lambda x: shelf["products"][x.product_uuid], customer.cart.values()))

    return render_template("user_index.html", customer=customer, products=products, products_in_cart=products_in_cart)

# the signup route
@app.route('/signup', methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        if not request.form.get("name")\
            or not request.form.get("email")\
            or not request.form.get("password")\
            or not request.form.get("re_password")\
            or not request.form.get("phonenumber")\
            or not request.form.get("address"):
                 flash("All form fields are required", category="danger")
                 return redirect(request.url)
        
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        re_password = request.form.get("re_password")
        phonenumber = request.form.get("phonenumber")
        address = request.form.get("address")

        if not phonenumber.replace('.','',1).isdecimal():
            flash("Contact Number must be numeric", category="danger")
            return redirect(request.url)

        if not password == re_password:
            flash("Passwords Don't match", category="warning")
            return redirect(request.url)
        
        customers = shelf["customers"].values()
        if email in list(map(lambda x: x.email, customers)):
            flash(Markup('Email Already Exists, <a href="/login">Login?</a>'), category="danger")
            return redirect(request.url)

        
        new_customer = Customer(name, email, phonenumber, password, address)
        shelf["customers"][new_customer.uuid] = new_customer
        shelf["account_creation_history"][generate_time_for_timeseries()] += 1
        flash("Account Created successfully", category="success")
        shelf.sync()
        return redirect("/login")
    
    return render_template("user_signup.html")

# the login route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not request.form.get("email") or not request.form.get("password"):
            flash("Please enter valid info", category="danger")
            return redirect(request.url)
        email = request.form.get("email")
        password = request.form.get("password")

        for customer in shelf.get("customers").values():
            print(customer.password)
            if customer.email == email:
                if customer.check_password(password):
                    session["customer_uuid"] = customer.uuid
                    flash("You're now logged in", category="success")
                    return redirect('/')
        flash("Incorrect email or passowrd", category="danger")
        return redirect(request.url)
    
    return render_template("user_login.html")

# route to add item to cart
@app.route("/add_to_cart", methods=["POST"])
@login_required
def add_to_cart():
    if not request.form.get("product_uuid"):
        return redirect("/")
    product_uuid = request.form.get("product_uuid")
    all_products = shelf["products"]
    if product_uuid not in all_products.keys():
        flash("Invalid Product", category="danger")
        return redirect("/")

    customer = shelf["customers"][session.get("customer_uuid")]
    products_in_cart = list(map(lambda x: shelf["products"][x.product_uuid], customer.cart.values()))

    if product_uuid in products_in_cart:
        flash("Product is already in cart", category="warning")
        return redirect("/cart")
    
    if shelf["products"][product_uuid].quantity < 1:
        flash("Out of stock", category="danger")
        return redirect("/")

    new_cart_item = CartItem(product_uuid, 1)
    shelf["customers"][customer.uuid].cart[new_cart_item.uuid] = new_cart_item
    shelf.sync()
    flash("Item Added to cart", category="success")
    return redirect("/cart")

# route for search products
@app.route("/search")
@login_required
def search():
    if not request.args.get("query"):
        flash("Please provide a query to search", category="warning")
        return redirect("/")
    
    q = request.args.get("query")
    customer = shelf["customers"][session.get("customer_uuid")]
    products_in_cart = list(map(lambda x: shelf["products"][x.product_uuid], customer.cart.values()))
    all_products = shelf["products"].values()
    
    products = [product for product in all_products if q.lower() in product.name.lower() or q in product.description.lower() or q in product.brand.lower() or q in product.uuid.lower()]

    return render_template("user_search.html", products_in_cart=products_in_cart, products=products, customer=customer, query=q)

# route for rewards
@app.route("/rewards", methods=["GET", "POST"])
@login_required
def rewards():
    if request.method == "POST":
        if not request.form.get("reward_uuid"):
            flash("ERROR", category="danger")
            return redirect("/reward")
        
        reward_uuid = request.form.get("reward_uuid")
        all_rewards = shelf["rewards"]

        if reward_uuid not in all_rewards.keys():
            flash("Invalid Reward", category="danger")
            return redirect("/")

        customer = shelf["customers"][session.get("customer_uuid")]
        customer_rewards = customer.rewards.values()
        reward = all_rewards[reward_uuid]

        if reward in customer_rewards:
            flash("You Already Have This", category="warning")
            return redirect("/")

        if reward.cost > customer.reward_points:
            flash("You don't have enough reward points", category="warning")
            return redirect("/rewards")

        shelf["customers"][customer.uuid].reward_points -= reward.cost
        
        reward = all_rewards[reward_uuid]
        new_reward = dataclasses.replace(reward)

        shelf["customers"][customer.uuid].rewards[reward_uuid] = new_reward
        flash("Added Reward!", category="success")
        return redirect("/")
    
    customer_uuid = session.get("customer_uuid")
    customer = shelf["customers"][customer_uuid]

    rewards = [reward for reward in shelf["rewards"].values() if reward.status == RewardStatus.VALID]
    customer_rewards = customer.rewards.values()
    return render_template("user_rewards.html", customer=customer, rewards=rewards, customer_rewards=customer_rewards)

# route for viewing cart and checking out
@app.route("/cart", methods=["GET", "POST"])
@login_required
def cart():
    if request.method == "POST":
        customer = shelf["customers"][session.get("customer_uuid")]

        cart_items = list(customer.cart.values())

        orders = []
        weights = []
        total_cost = 0

        for cart_item in cart_items:
            product = shelf["products"][cart_item.product_uuid]
            quantity = cart_item.quantity

            if quantity > product.quantity:
                flash(f"Not Enough Stocks for {product.name}", category="danger")
                flash(f"Removed {product.name} from cart", category="warning")
                shelf["customers"][session.get("customer_uuid")].cart.pop(cart_item.uuid, None)
                break
            
            cost = product.price * quantity
            order = Order(product, quantity, cost, customer.uuid)
            shelf["products"][cart_item.product_uuid].quantity -= quantity
            shelf["products"][cart_item.product_uuid].total_orders += 1
            shelf["orders_history"][generate_time_for_timeseries()] += 1


            total_cost += cost
            orders.append(order)
            shelf["customers"][session.get("customer_uuid")].cart.pop(cart_item.uuid, None)
            flash(f"Order placed for {product.name}", category="info")

        for order in orders:
            weights.append(order.cost / total_cost)

        discount = 0
        if request.form["reward"]:
            reward = shelf["customers"][session.get("customer_uuid")].rewards[request.form.get("reward")]
            discount = reward.calc_discount(total_cost)
            shelf["customers"][customer.uuid].rewards.pop(reward.uuid)

        for idx, order in enumerate(orders):
            order.cost = round(order.cost - (weights[idx] * discount), 2)
            shelf["customers"][customer.uuid].orders[order.uuid] = order

        shelf["customers"][customer.uuid].reward_points += int((total_cost * 100) * 0.05)
        shelf.sync()
        return redirect("/")



    
    all_products = shelf["products"]
    customer = shelf["customers"][session.get("customer_uuid")]
    customer_rewards = list(customer.rewards.values())

    return render_template("user_cart.html", customer=customer, products=all_products, customer_rewards=customer_rewards)

# route for viewing orders of the user and their status
@app.route("/orders")
@login_required
def orders():
    customer = shelf["customers"][session.get("customer_uuid")]
    orders = customer.orders

    all_orders = list(customer.orders.values())

    
    pending_orders = [order for order in all_orders if order.status == OrderStatus.APPROVAL_PENDING]
    shipped_orders = [order for order in all_orders if order.status == OrderStatus.SHIPPED]
    delivered_orders = [order for order in all_orders if order.status == OrderStatus.DELIVERED]
    refunded_orders = [order for order in all_orders if order.status == OrderStatus.REFUNDED]

    
    return render_template("user_orders.html", customer=customer, all_orders=all_orders,
                            pending_orders=pending_orders, 
                            shipped_orders=shipped_orders, 
                            delivered_orders=delivered_orders, 
                            refunded_orders=refunded_orders)

# route to delete a cart item
@login_required
def delete_cart_item():
    shelf["customers"][session.get("customer_uuid")].cart.pop(request.form.get("cart_item_uuid"), None)
    shelf.sync()
    return redirect("/cart")

# route to update the quantity of cart item
@app.route("/update_cart_item", methods=["POST"])
@login_required
def update_cart_item():
    if not request.form.get("quantity") or not request.form.get("cart_item_uuid"):
        flash("ERROR", category="danger")
        return redirect("/cart")
    
    quantity = request.form.get("quantity")
    cart_item_uuid = request.form.get("cart_item_uuid")
    customer = shelf["customers"][session.get("customer_uuid")]
    all_products = shelf["products"]
    product = all_products[customer.cart[cart_item_uuid].product_uuid]



    if cart_item_uuid not in customer.cart:
        flash("Not In cart", category="danger")
        return redirect("/cart")

    if not quantity.isdecimal():
        flash("ERROR", category="danger")
        return redirect("/")

    quantity = int(quantity)
    
    if quantity > product.quantity:
        flash("Not enough stocks", category="warning")
        flash("setting max", category="info")

    if quantity < 1:
        flash("minimum one", category="warning")
        return redirect("/cart")
    
    shelf["customers"][customer.uuid].cart[cart_item_uuid].quantity = min(shelf["products"][customer.cart[cart_item_uuid].product_uuid].quantity, quantity)
    flash("updated successfully", category="success")
    shelf.sync()
    return redirect("/cart")

# route to edit account info 
@app.route("/edit_account_info", methods = ['GET', 'POST'])
@login_required
def edit_account_info():
    if request.method == "POST":
        customer_uuid = session.get("customer_uuid")
        customer = shelf["customers"][customer_uuid]

        if not request.form.get("name")\
            or not request.form.get("email")\
            or not request.form.get("phonenumber")\
            or not request.form.get("address"):
                 flash("All form fields are required", category="danger")
                 return redirect(request.url)
        
        name = request.form.get("name")
        email = request.form.get("email")
        phonenumber = request.form.get("phonenumber")
        address = request.form.get("address")

        if not phonenumber.replace('.','',1).isdecimal():
            flash("Contact Number must be numeric", category="danger")
            return redirect(request.url)
        
        customers = shelf["customers"].values()
        if email in list(map(lambda x: x.email, customers)) and email != customer.email:
            flash("Email Already Exists", category="danger")
            return redirect(request.url)
        
        shelf["customers"][customer_uuid].name = name
        shelf["customers"][customer_uuid].email = email
        shelf["customers"][customer_uuid].phonenumber = phonenumber
        shelf["customers"][customer_uuid].address = address
        
        flash("Account Info Updated successfully", category="success")
        shelf.sync()
        return redirect("/")

    
    customer_uuid = session.get("customer_uuid")
    customer = shelf["customers"][session.get("customer_uuid")]
    return render_template("user_account_edit.html", customer=customer)

# route to clear the session and logout
@app.route('/logout')
def logout():
    session.clear()
    flash("Successfully Logged Out", category="success")
    return redirect("/login")

# The admin routes start here
# route for overviewing customer info
@app.route("/admin/customers")
@admin_only
def admin_customers():
    customers = shelf["customers"]
    total_customers = len(customers)
    
    return render_template("admin_customers.html", customers=customers, total_customers=total_customers)
    
# route to edit a customer's info
@app.route('/admin/customers/edit/<customer_uuid>', methods = ['GET', 'POST'])
@admin_only
def admin_customers_edit(customer_uuid):
    if request.method == 'POST':
        if not shelf["customers"].get(customer_uuid):
            abort(404)
        customer = shelf["customers"][customer_uuid]

        if not request.form.get("name")\
            or not request.form.get("email")\
            or not request.form.get("phonenumber")\
            or not request.form.get("address"):
                 flash("All form fields are required", category="danger")
                 return redirect(request.url)
        
        name = request.form.get("name")
        email = request.form.get("email")
        phonenumber = request.form.get("phonenumber")
        address = request.form.get("address")

        if not phonenumber.replace('.','',1).isdecimal():
            flash("Contact Number must be numeric", category="danger")
            return redirect(request.url)
        
        customers = shelf["customers"].values()
        if email in list(map(lambda x: x.email, customers)) and email != customer.email:
            flash("Email Already Exists", category="danger")
            return redirect(request.url)
        
        shelf["customers"][customer_uuid].name = name
        shelf["customers"][customer_uuid].email = email
        shelf["customers"][customer_uuid].phonenumber = phonenumber
        shelf["customers"][customer_uuid].address = address
        
        flash("Customer Info Updated successfully", category="success")
        shelf.sync()
        return redirect("/admin/customers")

    
    if not shelf["customers"].get(customer_uuid):
        abort(404)
    customer = shelf["customers"][customer_uuid]
    return render_template("admin_customers_edit.html", customer=customer)

# the admin dashboard pages
@app.route('/admin')
@app.route('/admin/dashboard')
@admin_only
def admin_dashboard():
    all_customers = shelf["customers"]
    all_orders = []

    for customer in all_customers.values():
        print(customer.uuid)
        all_orders.extend(list(customer.orders.values()))

    pending_orders = [order for order in all_orders if order.status == OrderStatus.APPROVAL_PENDING]
    total_orders = len(all_orders)
    total_customers = len(shelf["customers"])
    total_pedning_orders = len(pending_orders)
    
    return render_template("admin_dashboard.html", total_orders=total_orders, total_customers=total_customers, total_pedning_orders=total_pedning_orders)

# routes for generating graphs
@app.route("/graph/activity")
@login_required
def activity_graph():
    activity_history = shelf["activity_history"]

    fig = px.bar(x= activity_history.keys(), y=activity_history.values(), labels={"x" : "Date/Time", "y" : "Activity"}, title="Website Acitvity History")
    # as plotly only supports writing html to files, using temporary directory
    with TemporaryDirectory() as tmp_dir:
        filename = tmp_dir + "tmp.html"
        fig.write_html(filename)
        with open(filename, "r") as f:
            graph_html = f.read()

    return graph_html

@app.route("/graph/account_creation_history")
@login_required
def account_creation_history():
    account_creation_history = shelf["account_creation_history"]

    fig = px.bar(x= account_creation_history.keys(), y=account_creation_history.values(), labels={"x" : "Date/Time", "y" : "Activity"}, title="Account Creation History")
    with TemporaryDirectory() as tmp_dir:
        filename = tmp_dir + "tmp.html"
        fig.write_html(filename)
        with open(filename, "r") as f:
            graph_html = f.read()

    return graph_html

@app.route("/graph/orders_history")
@login_required
def orders_history():
    orders_history = shelf["orders_history"]

    fig = px.bar(x= orders_history.keys(), y=orders_history.values(), labels={"x" : "Date/Time", "y" : "Activity"}, title="Orders History")
    with TemporaryDirectory() as tmp_dir:
        filename = tmp_dir + "tmp.html"
        fig.write_html(filename)
        with open(filename, "r") as f:
            graph_html = f.read()

    return graph_html

# admin login route
@app.route('/admin/login', methods = ['GET', 'POST'])
def admin_login():
    if request.method == "POST":
        if not request.form.get('email') or not request.form.get('password'):
            flash("Please enter valid info", category="danger")
            return redirect(request.url)
        email = request.form.get("email")
        password = request.form.get("password")

        for admin in shelf.get("admins").values():
            if admin.email == email:
                if admin.check_password(password):
                    session["admin_uuid"] = admin.uuid
                    flash("You're now logged in", category="success")
                    return redirect('/admin')
        flash("Incorrect email or passowrd", category="danger")
        return redirect(request.url)
    return render_template("admin_login.html")

# admin route to add a product
@app.route('/admin/products/add', methods = ['GET', 'POST'])
@admin_only
def admin_products_add():
    if request.method == 'POST':
        if not request.form.get("name") or not request.form.get("brand") or not request.form.get("quantity")  \
            or not request.form.get("msrp") or not request.form.get("price") or not request.form.get("description")\
                 or "image-file" not in request.files or not request.form.get("supplier_uuid"):
                 flash("All form fields are required", category="danger")
                 return redirect(request.url)
        
        image_file = request.files['image-file']
        if image_file.filename == "":
            flash("Please select a file", category="danger")
            return redirect(request.url)
        if not (image_file and allowed_file(image_file.filename, ALLOWED_EXTENSIONS)):
            flash("File type not allowed", category="danger")
            return redirect(request.url)

        suppliers = shelf["suppliers"]
        ext = os.path.splitext(image_file.filename)[1]
        filename = str(uuid4()) + ext
        full_file_path = os.path.join("static", "uploads", filename)
        image_file.save(full_file_path)
        full_file_path = "/" + full_file_path
        
        name = request.form.get("name")
        brand = request.form.get("brand")
        quantity = request.form.get("quantity")
        msrp = request.form.get("msrp")
        price = request.form.get("price")
        supplier_uuid = request.form.get("supplier_uuid")
        description = request.form.get("description")

        if not msrp.replace('.','',1).isdecimal() or not price.replace('.','',1).isdecimal():
            flash("Prices must be numeric", category="danger")
            return redirect(request.url)
        if not quantity.isdecimal():
            flash("Quantity must be an integer", category="danger")
            return redirect(request.url)
        
        msrp = float(msrp)
        price = float(price)
        quantity = int(quantity)

        if supplier_uuid not in suppliers:
            flash("supplier not found", category="danger")
            return redirect(request.url)
        
        if not price < msrp:
            flash("Price should be less than or equal to MSRP", category="danger")
            return redirect(request.url)
        if not (quantity > 0 or msrp > 0 or price > 0):
            flash("Numberic fields should be greater than zero(0)", category="danger")
            return redirect(request.url)
        
        new_product = Product(name, description, brand, quantity, full_file_path, msrp, price, supplier_uuid)
        print("_"*50)
        print(new_product.uuid)
        print("_"*50)
        shelf["products"][new_product.uuid] = new_product
        flash("Product Added successfully", category="success")
        shelf.sync()
        return redirect(request.url)

    suppliers = shelf["suppliers"]
    return render_template("admin_products_add.html", suppliers=suppliers)

# admin route to edit a product's info
@app.route('/admin/products/edit/<product_uuid>', methods = ['GET', 'POST'])
@admin_only
def admin_products_edit(product_uuid):
    if request.method == 'POST':
        if not shelf["products"].get(product_uuid):
            abort(404)
        product = shelf["products"][product_uuid]
        
        if not request.form.get("name") or not request.form.get("brand") or not request.form.get("quantity") \
            or not request.form.get("msrp") or not request.form.get("price") or not request.form.get("description")\
                 or "image-file" not in request.files or not request.form.get("supplier_uuid"):
                 flash("All form fields are required", category="danger")
                 return redirect(request.url)
        
        image_file = request.files['image-file']
        print("*"*60)
        print(image_file.filename == "")
        if image_file.filename != "":
            if not (image_file and allowed_file(image_file.filename, ALLOWED_EXTENSIONS)):
                flash("File type not allowed", category="danger")
                return redirect(request.url)

            ext = os.path.splitext(image_file.filename)[1]
            filename = secure_filename(os.path.join(str(uuid4()), ext))
            full_file_path = os.path.join("static", "uploads", filename)
            image_file.save(full_file_path)
            full_file_path = "/" + full_file_path


        else:
            full_file_path = product.image_path

        name = request.form.get("name")
        brand = request.form.get("brand")
        quantity = request.form.get("quantity")
        msrp = request.form.get("msrp")
        price = request.form.get("price")
        description = request.form.get("description")
        supplier_uuid = request.form.get("supplier_uuid")
        suppliers = shelf["suppliers"]

        if supplier_uuid not in suppliers:
            flash("supplier not found", category="danger")
            return redirect(request.url)

        if not msrp.replace('.','',1).isdecimal() or not price.replace('.','',1).isdecimal():
            flash("Prices must be numeric", category="danger")
            return redirect(request.url)
        if not quantity.isdecimal():
            flash("Quantity must be an integer", category="danger")
            return redirect(request.url)
        
        msrp = float(msrp)
        price = float(price)
        quantity = int(quantity)

        if not price < msrp:
            flash("Price should be less than or equal to MSRP", category="danger")
            return redirect(request.url)
        if not (quantity > 0 or msrp > 0 or price > 0):
            flash("Numberic fields should be greater than zero(0)", category="danger")
            return redirect(request.url)
        

        shelf["products"][product_uuid].msrp = msrp
        shelf["products"][product_uuid].price = price
        shelf["products"][product_uuid].quantity = quantity
        shelf["products"][product_uuid].name = name
        shelf["products"][product_uuid].description = description
        shelf["products"][product_uuid].brand = brand
        shelf["products"][product_uuid].image_path = full_file_path
        shelf["products"][product_uuid].supplier_uuid = supplier_uuid


        flash("Product Updated successfully", category="success")
        shelf.sync()
        return redirect(request.url)

    if not shelf["products"].get(product_uuid):
        abort(404)
    
    suppliers = shelf["suppliers"]
    product = shelf["products"][product_uuid]
    return render_template("admin_products_edit.html", product=product, suppliers=suppliers)

# admin route to view products overview
@app.route('/admin/products')
@admin_only
def admin_products():
    products = shelf["products"]
    suppliers = shelf["suppliers"]
    total_products = len(products)
    total_stock = 0

    for product in products.values():
        total_stock += product.quantity
    return render_template("admin_products.html", products=products, total_products=total_products, total_stock=total_stock, suppliers=suppliers)

# admin route to add reward
@app.route('/admin/rewards/add', methods = ['GET', 'POST'])
@admin_only
def admin_rewards_add():
    if request.method == "POST":
        if not request.form.get("name") or not request.form.get("cost") or not request.form.get("max") \
            or not request.form.get("percent_discount"):
                 flash("All form fields are required", category="danger")
                 return redirect(request.url)
        
        name = request.form.get("name")
        cost = request.form.get("cost")
        max_discount = request.form.get("max")
        percent_discount = request.form.get("percent_discount")
        

        if not max_discount.replace('.','',1).isdecimal():
            flash("Max Discount must be numeric", category="danger")
            return redirect(request.url)
        if not cost.isdecimal() or not percent_discount.isdecimal():
            flash("Cost and Percent Discount must be an integer", category="danger")
            return redirect(request.url)
        
        cost = int(cost)
        percent_discount = int(percent_discount)
        max_discount = float(max_discount)
        
        if not (cost > 0 or percent_discount > 0 or max_discount > 0):
            flash("Numberic fields should be greater than zero(0)", category="danger")
            return redirect(request.url)

        new_reward = Reward(name, cost, percent_discount, max_discount)
        
        shelf["rewards"][new_reward.uuid] = new_reward
        flash("Reward Created successfully", category="success")
        shelf.sync()
        return redirect(request.url)
    return render_template("admin_rewards_add.html")

# admin route to view rewards
@app.route('/admin/rewards')
@admin_only
def admin_rewards():
    rewards = shelf["rewards"]
    total_rewards = len(rewards)
    valid_rewards = [reward for reward in rewards.values() if reward.status is RewardStatus.VALID]
    invalid_rewards = [reward for reward in rewards.values() if reward.status is RewardStatus.INVALID]

    return render_template("admin_rewards.html", rewards=rewards, total_rewards=total_rewards, invalid_rewards=invalid_rewards, valid_rewards=valid_rewards)

# admin route to update status of a reward
@app.route("/admin/rewards/update/<reward_uuid>", methods=["POST"])
@admin_only
def admin_rewards_update(reward_uuid):
    if reward_uuid in shelf["rewards"]:
        shelf["rewards"][reward_uuid].flip()
        flash("Reward Status Updated", category="success")
        return redirect("/admin/rewards")
    else:
        abort(404)

# admin route to view suppliers info
@app.route('/admin/suppliers')
@admin_only
def admin_suppliers():
    suppliers = shelf["suppliers"]
    products = shelf["products"]
    total_suppliers = len(suppliers)
    
    return render_template("admin_suppliers.html", suppliers=suppliers, total_suppliers=total_suppliers, products=products)

# admin route to add suppliers
@app.route('/admin/suppliers/add', methods = ['GET', 'POST'])
@admin_only
def admin_suppliers_add():
    if request.method == 'POST':
        if not request.form.get("company") or not request.form.get("website") \
             or not request.form.get("email") or not request.form.get("phonenumber")\
                 or not request.form.get("address"):
                 flash("All form fields are required", category="danger")
                 return redirect(request.url)
        
        name = request.form.get("company")
        website = request.form.get("website")
        # product_uuid = request.form.get("product")
        # cost = request.form.get("cost")
        email = request.form.get("email")
        phonenumber = request.form.get("phonenumber")
        address = request.form.get("address")

        # if not cost.replace('.','',1).isdecimal():
        #     flash("Cost must be numeric", category="danger")
        #     return redirect(request.url)
        if not phonenumber.isdecimal():
            flash("Phone Number must be an Numeric", category="danger")
            return redirect(request.url)

        # products = shelf["products"]
        # if not product_uuid in products:
        #     flash("Product Doesn't Exist", category="danger")
        #     return redirect(request.url)
        
        # cost = float(cost)

        
        # if not (cost):
        #     flash("Cost must be greater than zero(0)", category="danger")
        #     return redirect(request.url)
        
        new_supplier = Supplier(name, address, website, phonenumber, email)
        print("*"*60)
        print(new_supplier.uuid)
        shelf["suppliers"][new_supplier.uuid] = new_supplier
        flash("Supplier Added successfully", category="success")
        shelf.sync()
        return redirect("/admin/suppliers")

    products = shelf["products"]
    return render_template("admin_suppliers_add.html", products=products)

# admin route to edit suppliers
@app.route("/admin/suppliers/edit/<supplier_uuid>", methods = ["GET", "POST"])
@admin_only
def admin_suppliers_edit(supplier_uuid):
    if request.method == 'POST':
        if not shelf["suppliers"].get(supplier_uuid):
            abort(404)
        supplier = shelf["suppliers"][supplier_uuid]

        if not request.form.get("company") or not request.form.get("website") \
            or not request.form.get("email") or not request.form.get("phonenumber")\
                 or not request.form.get("address"):
                 flash("All form fields are required", category="danger")
                 return redirect(request.url)
        
        name = request.form.get("company")
        website = request.form.get("website")
        email = request.form.get("email")
        phonenumber = request.form.get("phonenumber")
        address = request.form.get("address")

        
        if not phonenumber.isdecimal():
            flash("Phone Number must be an Numeric", category="danger")
            return redirect(request.url)
        
        shelf["suppliers"][supplier_uuid].company = name
        shelf["suppliers"][supplier_uuid].website = website
        shelf["suppliers"][supplier_uuid].email = email
        shelf["suppliers"][supplier_uuid].phonenumber = phonenumber
        shelf["suppliers"][supplier_uuid].address = address

        
        flash("Supplier Updated successfully", category="success")
        shelf.sync()
        return redirect("/admin/suppliers")

    
    if not shelf["suppliers"].get(supplier_uuid):
        abort(404)
    supplier = shelf["suppliers"][supplier_uuid]
    return render_template("admin_suppliers_edit.html", supplier=supplier)

# admin route to manage orders
@app.route("/admin/orders")
@admin_only
def admin_orders():
    all_customers = shelf["customers"]
    all_orders = []

    for customer in all_customers.values():
        print(customer.uuid)
        all_orders.extend(list(customer.orders.values()))
    
    pending_orders = [order for order in all_orders if order.status == OrderStatus.APPROVAL_PENDING]
    shipped_orders = [order for order in all_orders if order.status == OrderStatus.SHIPPED]
    delivered_orders = [order for order in all_orders if order.status == OrderStatus.DELIVERED]
    refunded_orders = [order for order in all_orders if order.status == OrderStatus.REFUNDED]

    return render_template("admin_orders.html", all_orders=all_orders, all_customers=all_customers,
                            pending_orders=pending_orders, 
                            shipped_orders=shipped_orders, 
                            delivered_orders=delivered_orders, 
                            refunded_orders=refunded_orders)

# admin route to update a order's info
@app.route("/admin/orders/update", methods=["POST"])
@admin_only
def update_order():
    if not request.form.get("order_uuid") or not request.form.get("status") or not request.form.get("customer_uuid"):
        flash("ERROR", category="danger")
        return redirect("/admin/orders")
    
    order_uuid = request.form.get("order_uuid")
    customer_uuid = request.form.get("customer_uuid")
    status = request.form.get("status")

    if status == OrderStatus.APPROVAL_PENDING.value:
        shelf["customers"][customer_uuid].orders[order_uuid].status = OrderStatus.APPROVAL_PENDING
    elif status == OrderStatus.DELIVERED.value:
        shelf["customers"][customer_uuid].orders[order_uuid].status = OrderStatus.DELIVERED
    elif status == OrderStatus.SHIPPED.value:
        shelf["customers"][customer_uuid].orders[order_uuid].status = OrderStatus.SHIPPED
    elif status == OrderStatus.REFUNDED.value:
        shelf["customers"][customer_uuid].orders[order_uuid].status = OrderStatus.REFUNDED

    shelf.sync()

    flash("updated successfully", category="success")
    return redirect("/admin/orders")

# admin logout
@app.route('/admin/logout')
@admin_only
def admin_logout():
    session.pop('admin_uuid')
    flash("You've been logged out successfully", category="success")
    return redirect("/admin/login")

# checking if the file is run directly or called in as a module (i.e flask run command for example)
if __name__ == "__main__":
    app.run(host="0.0.0.0")
    shelf.sync()
    shelf.close()
