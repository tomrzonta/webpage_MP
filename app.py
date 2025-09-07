import os
import click
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

# --- CONFIGURAÇÃO E INICIALIZAÇÃO DA APLICAÇÃO ---
app = Flask(__name__)
# ... (resto da configuração sem mudanças)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-dificil'

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --- MODELOS DO BANCO DE DADOS ---
# ... (nenhuma mudança nos modelos)
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(60), nullable=False)
    sector_name = db.Column(db.String(50), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)

class Sector(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    subcategories = db.relationship('Subcategory', back_populates='sector', lazy=True, cascade="all, delete-orphan")
    def __str__(self):
        return self.name

class Subcategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sector_id = db.Column(db.Integer, db.ForeignKey('sector.id'), nullable=False)
    sector = db.relationship('Sector', back_populates='subcategories')
    links = db.relationship('Link', back_populates='subcategory', lazy=True, cascade="all, delete-orphan")
    def __str__(self):
        return self.name

class Link(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    subcategory_id = db.Column(db.Integer, db.ForeignKey('subcategory.id'), nullable=False)
    subcategory = db.relationship('Subcategory', back_populates='links')
    def __str__(self):
        return self.name

# --- CONFIGURAÇÃO DO PAINEL ADMIN SEGURO (COM CUSTOMIZAÇÕES) ---
from flask_admin.model.form import InlineFormAdmin
from flask_admin.model.fields import InlineFormField, InlineFieldList
from flask_admin.form import form
from flask_admin.form.fields import Select2Field
from sqlalchemy.orm import backref

class AdminView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin
    def inaccessible_callback(self, name, **kwargs):
        flash('Você precisa ser um administrador para acessar esta página.', 'danger')
        return redirect(url_for('login'))

class SubcategoryAdminView(AdminView):
    form_columns = ['name', 'sector']
    # ADICIONAMOS ESTA LINHA PARA SIMPLIFICAR O FORMULÁRIO
    form_ajax_refs = {
        'sector': {
            'fields': ['name']
        }
    }

class LinkAdminView(AdminView):
    column_list = ['name', 'url', 'subcategory']
    form_columns = ['name', 'url', 'subcategory']
    # ADICIONAMOS ESTA LINHA PARA SIMPLIFICAR O FORMULÁRIO
    form_ajax_refs = {
        'subcategory': {
            'fields': ['name']
        }
    }


admin = Admin(app, name='Painel de Controle', template_mode='bootstrap4')

admin.add_view(AdminView(Sector, db.session, name='Setores'))
admin.add_view(SubcategoryAdminView(Subcategory, db.session, name='Subcategorias'))
admin.add_view(LinkAdminView(Link, db.session, name='Links'))

# --- ROTAS E COMANDOS ---
# ... (nenhuma outra mudança no resto do arquivo)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and bcrypt.check_password_hash(user.password_hash, request.form.get('password')):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login sem sucesso. Verifique e-mail e senha.', 'danger')
    return render_template('login.html', title='Login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_password = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')
        user = User(email=request.form.get('email'), password_hash=hashed_password, sector_name=request.form.get('sector'), is_admin=False)
        db.session.add(user)
        db.session.commit()
        flash('Sua conta foi criada! Você já pode fazer login.', 'success')
        return redirect(url_for('login'))
    sectors = Sector.query.all()
    return render_template('register.html', title='Registrar', sectors=sectors)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    user_sector = current_user.sector_name
    return redirect(url_for('view_sector_dashboard', sector_name=user_sector))

@app.route('/setor/<sector_name>')
@login_required
def view_sector_dashboard(sector_name):
    all_sectors = Sector.query.all()
    current_sector = Sector.query.filter_by(name=sector_name).first_or_404()
    if not current_user.is_admin and current_sector.name != current_user.sector_name:
        flash('Você não tem permissão para acessar este setor.', 'danger')
        return redirect(url_for('dashboard'))
    subcategories_for_sidebar = current_sector.subcategories
    active_subcategory_name = request.args.get('view', None)
    links_to_show = []
    if active_subcategory_name:
        for sub in subcategories_for_sidebar:
            if sub.name == active_subcategory_name:
                links_to_show = sub.links
                break
    return render_template('dashboard.html',
                           all_sectors=all_sectors,
                           current_sector=current_sector,
                           subcategories=subcategories_for_sidebar,
                           active_subcategory_name=active_subcategory_name,
                           links_to_show=links_to_show)

@app.cli.command('create-admin')
@click.option('--email', prompt=True, help='O e-mail do administrador.')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='A senha do administrador.')
def create_admin_command(email, password):
    """Cria um novo usuário administrador."""
    if User.query.filter_by(email=email).first():
        print(f'Erro: O e-mail {email} já existe.')
        return
    
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    admin_sector = Sector.query.first()
    if not admin_sector:
        print('Erro: Crie ao menos um setor antes de criar um admin. Rode "flask populate-db" primeiro.')
        return
        
    admin = User(email=email, password_hash=hashed_password, sector_name=admin_sector.name, is_admin=True)
    db.session.add(admin)
    db.session.commit()
    print(f'Administrador {email} criado com sucesso!')

@app.cli.command('populate-db')
def populate_db_command():
    pass # Desativado