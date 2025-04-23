from flask import Flask, render_template, request, redirect, session, flash, g
from flask_socketio import SocketIO, emit
import sqlite3

# Flask App
app = Flask(__name__)
app.config['SECRET_KEY'] = 'SECRET'
socketio = SocketIO(app)

# DB
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('market.db')
        g.db.row_factory = sqlite3.Row
        g.cursor = g.db.cursor()
    return g.db, g.cursor

# DB 초기화 함수
def init_db():
    db, cursor = get_db()
    # 유저 정보
    cursor.execute('''CREATE TABLE IF NOT EXISTS users
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password TEXT, balance INTEGER)''')
    # 상품 정보
    cursor.execute('''CREATE TABLE IF NOT EXISTS products
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                     name TEXT, 
                     price TEXT, 
                     description TEXT,
                     user_id INTEGER,
                     FOREIGN KEY(user_id) REFERENCES users(id))''')
    db.commit()

@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'db'):
        g.db.close()

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect('/dashboard')
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login_post():
    username = request.form['username']
    password = request.form['password']
    db, cursor = get_db()
    cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
    user = cursor.fetchone()
    if user :
        session['user_id'] = user['id']
        return redirect('/dashboard')
    else:
        flash('아이디 또는 비밀번호가 일치하지 않습니다.')
        return redirect('/login')
        
@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/register', methods=['POST'])
def register_post():
    username = request.form['username']
    password = request.form['password']
    # 중복 체크
    db, cursor = get_db()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    if cursor.fetchone():
        flash('이미 존재하는 아이디입니다.')
        return redirect('/register')
    # 회원가입
    default_balance = 10000
    cursor.execute('INSERT INTO users (username, password, balance) VALUES (?, ?, ?)', (username, password, default_balance))
    db.commit()
    return redirect('/login')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/dashboard')
def dashboard():
    # 로그인 여부 확인
    if 'user_id' not in session:
        return redirect('/login')
    # 유저 정보 조회
    db, cursor = get_db()
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    # 상품 정보 조회
    cursor.execute('SELECT * FROM products')
    products = cursor.fetchall()

    return render_template('dashboard.html', username=user['username'], products=products)

@app.route('/add_product')
def add_product():
    return render_template('add_product.html')

@app.route('/add_product', methods=['POST'])
def add_product_post():
    if 'user_id' not in session:
        return redirect('/login')
        
    name = request.form['name']
    price = request.form['price']
    description = request.form['description']
    db, cursor = get_db()
    cursor.execute('INSERT INTO products (name, price, description, user_id) VALUES (?, ?, ?, ?)', 
                  (name, price, description, session['user_id']))
    db.commit()
    return redirect('/dashboard')

@app.route('/product/<int:product_id>')
def product(product_id):
    db, cursor = get_db()
    cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
    product = cursor.fetchone()
    cursor.execute('SELECT * FROM users WHERE id = ?', (product['user_id'],))
    user = cursor.fetchone()
    return render_template('product.html', product=product, user=user)

@app.route('/transfer')
def transfer():
    if 'user_id' not in session:
        return redirect('/login')
        
    db, cursor = get_db()
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    if not user:
        flash('사용자 정보를 찾을 수 없습니다.')
        return redirect('/login')
        
    return render_template('transfer.html', username=user['username'], balance=user['balance'])

@app.route('/transfer', methods=['POST'])
def transfer_post():
    username = request.form['username']
    amount = request.form['amount']
    db, cursor = get_db()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()

    if session['user_id'] == user['id']:
        flash('자기 자신에게 송금할 수 없습니다.')
        return redirect('/transfer')

    if not user:
        flash('송금할 사용자를 찾을 수 없습니다.')
        return redirect('/transfer')
    
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    sender = cursor.fetchone()
    if sender['balance'] < int(amount):
        flash('잔액이 부족합니다.')
        return redirect('/transfer')
    
    # 송금자의 잔액 감소
    cursor.execute('UPDATE users SET balance = balance - ? WHERE id = ?', (int(amount), session['user_id']))
    # 수신자의 잔액 증가
    cursor.execute('UPDATE users SET balance = balance + ? WHERE id = ?', (int(amount), user['id']))
    
    db.commit()
    flash('송금이 완료되었습니다.')
    return redirect('/transfer')

@app.route('/report')
def report():
    return render_template('report.html')

@app.route('/report', methods=['POST'])
def report_post():
    username = request.form['username']
    product_id = request.form['product_id']
    reason = request.form['reason']
    # 신고 내용을 reports.txt 파일에 저장
    with open('reports.txt', 'a', encoding='utf-8') as f:
        f.write(f'Username: {username}\n')
        f.write(f'Product ID: {product_id}\n') 
        f.write(f'Reason: {reason}\n')
        f.write('-' * 50 + '\n')
    return redirect('/dashboard')

@app.route('/chat')
def chat():
    return render_template('chat.html')

@socketio.on('message')
def handle_message(data):
    # 유저 정보 조회 
    db, cursor = get_db()
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    emit('message', {'username': user['username'], 'message': data['message']}, broadcast=True)

if __name__ == '__main__':
    with app.app_context():
        init_db()
    socketio.run(app, debug=True)
    db, cursor = get_db()
    db.close()