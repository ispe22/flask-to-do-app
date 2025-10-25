from flask import render_template, redirect, url_for, request, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, current_user, logout_user
from dateutil.parser import parse

from app import app, db
from models import User, TodoList, Todo


@app.route("/")
def home():
    if current_user.is_authenticated:
        first_list = db.session.query(TodoList).order_by(TodoList.created_at).first()
        if first_list:
            return redirect(url_for('view_list', list_id=first_list.id))
    return view_list(list_id=0)


@app.route('/register', methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == "POST":
        username = request.form.get('username')
        if db.session.query(User).filter_by(username=username).first():
            flash("That username is already taken.", "warning")
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(request.form.get("password"), method='pbkdf2:sha256:600000', salt_length=8)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        flash("Account created successfully!", "success")
        return redirect(url_for('home'))
    return render_template("register.html")


@app.route('/login', methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == "POST":
        password = request.form.get("password") 
        username = request.form.get("username") 
        remember = True if request.form.get('remember') else False
        user = db.session.query(User).filter_by(username=username).first()

        if not user or not check_password_hash(user.password, password):
            flash("Invalid username or password. Please try again.", "danger")
            return redirect(url_for('login'))

        login_user(user, remember=remember)
        return redirect(url_for("home"))
    return render_template("login.html")


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route("/list/<int:list_id>")
def view_list(list_id):
    if current_user.is_authenticated:
        lists = db.session.query(TodoList).filter_by(owner=current_user).order_by(TodoList.created_at).all()
        current_list = db.session.query(TodoList).filter_by(id=list_id, user_id=current_user.id).first()
        if not current_list and lists:
            return redirect(url_for('view_list', list_id=lists[0].id))
        todos = db.session.query(Todo).filter_by(list_id=current_list.id).order_by(Todo.position).all() if current_list else []
        return render_template("index.html", lists=lists, current_list=current_list, todos=todos)
    else:
        # Guest/Demo mode
        lists = [TodoList(id=0, name="Demo list")]
        current_list = lists[0]
        todos = [
            Todo(id=1, task="Welcome to the demo!", done=False, position=1),
            Todo(id=2, task="You can drag tasks, but all buttons are disabled.", done=False, position=2),
            Todo(id=3, task="Sign up to create and save your own lists (only username and passoword needed).", done=False, position=3),
            Todo(id=4, task="This is a completed task.", done=True, position=4),
        ]
        return render_template("index.html", lists=lists, current_list=current_list, todos=todos)


@app.route("/add_list", methods=["POST"])
@login_required
def add_list():
    list_name = request.form.get("new_list_name", "").strip()
    if list_name:
        if db.session.query(TodoList).filter_by(name=list_name, owner=current_user).first():
            flash(f"A list named '{list_name}' already exists.", "warning")
            referer_url = request.referrer
            return redirect(referer_url or url_for('home'))
        else:
            new_list = TodoList(name=list_name, owner=current_user)
            db.session.add(new_list)
            db.session.commit()
            flash(f"List '{list_name}' created successfully.", "success")
            return redirect(url_for('view_list', list_id=new_list.id))

    return redirect(url_for('home'))


@app.route("/edit_list/<int:list_id>", methods=["POST"])
@login_required
def edit_list(list_id):
    todolist = db.get_or_404(TodoList, list_id)
    new_name = request.form.get("new_list_name", "").strip()
    if new_name:
        existing_list = db.session.query(TodoList).filter(TodoList.name == new_name, TodoList.id != list_id).first()
        if existing_list:
            flash(f"A list named '{new_name}' already exists.", "warning")
        else:
            todolist.name = new_name
            db.session.commit()
            flash("List name updated.", "success")
    return redirect(url_for("view_list", list_id=list_id))


@app.route("/delete_list/<int:list_id>", methods=["POST"])
@login_required
def delete_list(list_id):
    todolist = db.get_or_404(TodoList, list_id)
    db.session.delete(todolist)
    db.session.commit()
    flash(f"List '{todolist.name}' was deleted.", "success")
    return redirect(url_for("home"))


@app.route("/add_task/<int:list_id>", methods=["POST"])
def add_task(list_id):
    task_text = request.form.get("task", "").strip()
    if task_text:
        due_date_str = request.form.get("due_date")
        due_date = parse(due_date_str).date() if due_date_str else None
        max_pos = db.session.query(db.func.max(Todo.position)).filter_by(list_id=list_id).scalar() or 0
        new_task = Todo(task=task_text, list_id=list_id, due_date=due_date, position=max_pos + 1)
        db.session.add(new_task)
        db.session.commit()
    return redirect(url_for("view_list", list_id=list_id))


@app.route("/edit_task/<int:task_id>", methods=["POST"])
def edit_task(task_id):
    todo = db.get_or_404(Todo, task_id)
    task_text = request.form.get("task", "").strip()
    if task_text:
        todo.task = task_text
        due_date_str = request.form.get("due_date")
        todo.due_date = parse(due_date_str).date() if due_date_str else None
        db.session.commit()
    return redirect(url_for("view_list", list_id=todo.list_id))


@app.route("/toggle_task/<int:task_id>", methods=["POST"])
def toggle_task(task_id):
    todo = db.get_or_404(Todo, task_id)
    todo.done = not todo.done
    db.session.commit()
    return redirect(url_for("view_list", list_id=todo.list_id))


@app.route("/delete_task/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    todo = db.get_or_404(Todo, task_id)
    list_id = todo.list_id
    db.session.delete(todo)
    db.session.commit()
    return redirect(url_for("view_list", list_id=list_id))


@app.route("/reorder_tasks", methods=["POST"])
def reorder_tasks():
    data = request.json
    ordered_ids = data.get('task_ids', [])
    for index, task_id in enumerate(ordered_ids):
        task = db.get_or_404(Todo, int(task_id))
        task.position = index + 1
    db.session.commit()
    return jsonify(success=True)