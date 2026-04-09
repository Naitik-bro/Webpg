from flask import Flask, render_template, request, redirect, session, jsonify
from werkzeug.utils import secure_filename
from db import get_connection, init_db
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-this")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@gmail.com")

UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

init_db()


def get_cart_count(user_id):
    con = get_connection()
    cur = con.cursor()
    cur.execute("SELECT COALESCE(SUM(quantity), 0) FROM cart WHERE user_id = ?", (user_id,))
    result = cur.fetchone()[0]
    con.close()
    return int(result) if result else 0


# ---------------- AUTH ----------------

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"].strip()

        con = get_connection()
        cur = con.cursor()

        cur.execute("SELECT id FROM users WHERE email = ?", (email,))
        existing_user = cur.fetchone()

        if existing_user:
            con.close()
            return "Email already exists. Try another email."

        cur.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            (name, email, password),
        )
        con.commit()
        con.close()

        return redirect("/login")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"].strip()

        con = get_connection()
        cur = con.cursor()
        cur.execute(
            "SELECT * FROM users WHERE email = ? AND password = ?",
            (email, password),
        )
        user = cur.fetchone()
        con.close()

        if user:
            session["user_id"] = user["id"]
            session["email"] = user["email"]
            return redirect("/")
        else:
            return "Invalid credentials"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------- HOME / BOOKS ----------------

@app.route("/")
def home():
    if "user_id" not in session:
        return render_template("auth.html")
    return redirect("/books")


@app.route("/books")
def books():
    if "user_id" not in session:
        return redirect("/")

    con = get_connection()
    cur = con.cursor()
    cur.execute("SELECT * FROM books ORDER BY trending DESC, id DESC")
    books_data = cur.fetchall()
    con.close()

    cart_count = get_cart_count(session["user_id"])
    return render_template("books.html", books=books_data, cart_count=cart_count)


# ---------------- CART ----------------

@app.route("/add/<int:book_id>")
def add_to_cart(book_id):
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    con = get_connection()
    cur = con.cursor()

    cur.execute(
        "SELECT * FROM cart WHERE user_id = ? AND book_id = ?",
        (user_id, book_id),
    )
    item = cur.fetchone()

    if item:
        cur.execute(
            "UPDATE cart SET quantity = quantity + 1 WHERE id = ?",
            (item["id"],),
        )
    else:
        cur.execute(
            "INSERT INTO cart (user_id, book_id, quantity) VALUES (?, ?, 1)",
            (user_id, book_id),
        )

    con.commit()
    con.close()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True})

    return redirect("/books")


@app.route("/cart")
def cart():
    if "user_id" not in session:
        return redirect("/login")

    con = get_connection()
    cur = con.cursor()
    cur.execute(
        """
        SELECT books.title, books.author, books.price, books.images,
               cart.quantity, cart.book_id
        FROM cart
        JOIN books ON cart.book_id = books.id
        WHERE cart.user_id = ?
        """,
        (session["user_id"],),
    )
    items = cur.fetchall()
    con.close()

    total = sum(item["price"] * item["quantity"] for item in items)
    return render_template("cart.html", items=items, total=total)


@app.route("/remove/<int:book_id>")
def remove_item(book_id):
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    con = get_connection()
    cur = con.cursor()
    cur.execute(
        "DELETE FROM cart WHERE user_id = ? AND book_id = ?",
        (user_id, book_id),
    )
    con.commit()
    con.close()

    return redirect("/cart")


# ---------------- ADMIN ----------------

@app.route("/admin")
def admin():
    if session.get("email") != ADMIN_EMAIL:
        return "Access Denied"

    con = get_connection()
    cur = con.cursor()
    cur.execute("SELECT * FROM books ORDER BY id DESC")
    books_data = cur.fetchall()
    con.close()

    return render_template("admin.html", books=books_data)


@app.route("/add_book", methods=["POST"])
def add_book():
    if session.get("email") != ADMIN_EMAIL:
        return "Access Denied"

    title = request.form["title"].strip()
    author = request.form["author"].strip()
    price = request.form["price"]
    original_price = request.form.get("original_price") or None
    category = request.form.get("category", "").strip()
    trending = 1 if request.form.get("trending") == "on" else 0

    file = request.files.get("image")
    if not file or file.filename == "":
        return "Please upload an image"

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    con = get_connection()
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO books (title, author, price, original_price, images, category, trending)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (title, author, float(price), original_price, filename, category, trending),
    )
    con.commit()
    con.close()

    return redirect("/admin")


@app.route("/toggle_trending/<int:id>")
def toggle_trending(id):
    if session.get("email") != ADMIN_EMAIL:
        return "Access Denied"

    con = get_connection()
    cur = con.cursor()
    cur.execute("SELECT trending FROM books WHERE id = ?", (id,))
    book = cur.fetchone()

    if not book:
        con.close()
        return "Book not found"

    new_val = 0 if book["trending"] else 1
    cur.execute("UPDATE books SET trending = ? WHERE id = ?", (new_val, id))
    con.commit()
    con.close()

    return redirect("/admin")


@app.route("/delete/<int:id>")
def delete_book(id):
    if session.get("email") != ADMIN_EMAIL:
        return "Access Denied"

    con = get_connection()
    cur = con.cursor()
    cur.execute("DELETE FROM books WHERE id = ?", (id,))
    con.commit()
    con.close()

    return redirect("/admin")


@app.route("/edit/<int:id>")
def edit_book(id):
    if session.get("email") != ADMIN_EMAIL:
        return "Access Denied"

    con = get_connection()
    cur = con.cursor()
    cur.execute("SELECT * FROM books WHERE id = ?", (id,))
    book = cur.fetchone()
    con.close()

    if not book:
        return "Book not found"

    return render_template("edit.html", book=book)


@app.route("/update/<int:id>", methods=["POST"])
def update_book(id):
    if session.get("email") != ADMIN_EMAIL:
        return "Access Denied"

    title = request.form["title"].strip()
    author = request.form["author"].strip()
    price = request.form["price"]

    con = get_connection()
    cur = con.cursor()
    cur.execute(
        "UPDATE books SET title = ?, author = ?, price = ? WHERE id = ?",
        (title, author, float(price), id),
    )
    con.commit()
    con.close()

    return redirect("/admin")


# ---------------- BOOK DETAIL / SEARCH / FILTER ----------------

@app.route("/book/<int:id>")
def book_detail(id):
    if "user_id" not in session:
        return redirect("/")

    con = get_connection()
    cur = con.cursor()
    cur.execute("SELECT * FROM books WHERE id = ?", (id,))
    book = cur.fetchone()
    con.close()

    if not book:
        return "Book not found"

    return render_template("book_detail.html", book=book)


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()

    con = get_connection()
    cur = con.cursor()
    cur.execute("SELECT * FROM books WHERE title LIKE ?", ("%" + q + "%",))
    books_data = cur.fetchall()
    con.close()

    cart_count = get_cart_count(session["user_id"]) if "user_id" in session else 0
    return render_template("books.html", books=books_data, cart_count=cart_count)


@app.route("/filter")
def filter_books():
    category = request.args.get("category")
    trending = request.args.get("trending")

    con = get_connection()
    cur = con.cursor()

    if trending:
        cur.execute("SELECT * FROM books WHERE trending = 1 ORDER BY trending DESC, id DESC")
    elif category:
        cur.execute(
            "SELECT * FROM books WHERE category = ? ORDER BY trending DESC, id DESC",
            (category,),
        )
    else:
        cur.execute("SELECT * FROM books ORDER BY trending DESC, id DESC")

    books_data = cur.fetchall()
    con.close()

    cart_count = get_cart_count(session["user_id"]) if "user_id" in session else 0
    return render_template("books.html", books=books_data, cart_count=cart_count)


# ---------------- CHECKOUT / ORDERS ----------------

@app.route("/checkout")
def checkout():
    if "user_id" not in session:
        return redirect("/")
    return render_template("checkout.html")


@app.route("/place_order", methods=["POST"])
def place_order():
    if "user_id" not in session:
        return redirect("/")

    user_id = session["user_id"]
    address = request.form.get("address", "").strip()
    phone = request.form.get("phone", "").strip()

    if not address or not phone:
        return "Address and phone are required"

    con = get_connection()
    cur = con.cursor()

    cur.execute(
        """
        SELECT books.price, cart.quantity, cart.book_id
        FROM cart
        JOIN books ON cart.book_id = books.id
        WHERE cart.user_id = ?
        """,
        (user_id,),
    )
    items = cur.fetchall()

    if not items:
        con.close()
        return "Cart is empty"

    total = sum(item["price"] * item["quantity"] for item in items)

    cur.execute(
        "INSERT INTO orders (user_id, total, address, phone) VALUES (?, ?, ?, ?)",
        (user_id, total, address, phone),
    )
    order_id = cur.lastrowid

    for item in items:
        cur.execute(
            "INSERT INTO order_items (order_id, book_id, quantity) VALUES (?, ?, ?)",
            (order_id, item["book_id"], item["quantity"]),
        )

    cur.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
    con.commit()
    con.close()

    return render_template("thankyou.html")


@app.route("/orders")
def orders():
    if "user_id" not in session:
        return redirect("/")

    user_id = session["user_id"]
    con = get_connection()
    cur = con.cursor()

    cur.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC", (user_id,))
    orders_data = cur.fetchall()

    for order in orders_data:
        cur.execute(
            """
            SELECT books.title, order_items.quantity
            FROM order_items
            JOIN books ON order_items.book_id = books.id
            WHERE order_items.order_id = ?
            """,
            (order["id"],),
        )
        order["products"] = cur.fetchall()

    con.close()
    return render_template("orders.html", orders=orders_data)


@app.route("/admin_orders")
def admin_orders():
    if session.get("email") != ADMIN_EMAIL:
        return "Access Denied"

    con = get_connection()
    cur = con.cursor()

    cur.execute(
        """
        SELECT orders.id, orders.total, orders.address, orders.phone,
               orders.status, users.email
        FROM orders
        JOIN users ON orders.user_id = users.id
        ORDER BY orders.id DESC
        """
    )
    orders_data = cur.fetchall()

    for order in orders_data:
        cur.execute(
            """
            SELECT books.title, order_items.quantity
            FROM order_items
            JOIN books ON order_items.book_id = books.id
            WHERE order_items.order_id = ?
            """,
            (order["id"],),
        )
        order["products"] = cur.fetchall()

    con.close()
    return render_template("admin_orders.html", orders=orders_data)


@app.route("/update_order_status/<int:order_id>/<status>")
def update_order_status(order_id, status):
    if session.get("email") != ADMIN_EMAIL:
        return "Access Denied"

    allowed_status = ["Pending", "Cancelled", "Done"]
    if status not in allowed_status:
        return "Invalid status"

    con = get_connection()
    cur = con.cursor()
    cur.execute(
        "UPDATE orders SET status = ? WHERE id = ?",
        (status, order_id),
    )
    con.commit()
    con.close()

    return redirect("/admin_orders")


if __name__ == "__main__":
    app.run(debug=True)