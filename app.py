import os
import click
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_admin.menu import MenuLink

# --- CONFIGURAÇÃO E INICIALIZAÇÃO DA APLICAÇÃO ---
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-dificil'

db = SQLAlchemy(app)

# --- TABELA DE ASSOCIAÇÃO ---
user_sectors_association = db.Table('user_sectors',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('sector_id', db.Integer, db.ForeignKey('sector.id'), primary_key=True)
)

bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --- MODELOS DO BANCO DE DADOS ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(60), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    sectors = db.relationship('Sector', secondary=user_sectors_association, lazy='subquery',
                             back_populates='users')

class Sector(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    subcategories = db.relationship('Subcategory', back_populates='sector', lazy=True, cascade="all, delete-orphan")
    users = db.relationship('User', secondary=user_sectors_association, lazy='subquery',
                           back_populates='sectors')
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

# --- CONFIGURAÇÃO DO PAINEL ADMIN ---
class SecureModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin
    def inaccessible_callback(self, name, **kwargs):
        flash('Você precisa ser um administrador para acessar esta página.', 'danger')
        return redirect(url_for('login'))

class UserAdminView(SecureModelView):
    form_columns = ['email', 'is_admin', 'sectors']
    column_list = ['email', 'is_admin', 'sectors']
    form_ajax_refs = { 'sectors': { 'fields': ['name'] } }

class SectorAdminView(SecureModelView):
    can_create = False
    column_list = ['name', 'subcategories']
    column_searchable_list = ['name']

class SubcategoryAdminView(SecureModelView):
    form_columns = ['name', 'sector']
    form_ajax_refs = { 'sector': { 'fields': ['name'] } }
    column_searchable_list = ['name']

class LinkAdminView(SecureModelView):
    column_list = ['name', 'url', 'subcategory']
    form_columns = ['name', 'url', 'subcategory']
    form_ajax_refs = { 'subcategory': { 'fields': ['name'] } }
    column_searchable_list = ['name']


admin = Admin(app, name='Painel de Controle', template_mode='bootstrap4')
admin.add_view(UserAdminView(User, db.session, name='Usuários'))
admin.add_view(SectorAdminView(Sector, db.session, name='Setores'))
admin.add_view(SubcategoryAdminView(Subcategory, db.session, name='Subcategorias'))
admin.add_view(LinkAdminView(Link, db.session, name='Links'))
admin.add_link(MenuLink(name='Voltar para a Aplicação', category='', url='/'))

# --- ROTAS DE AUTENTICAÇÃO ---
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
        selected_sector_name = request.form.get('sector')
        sector = Sector.query.filter_by(name=selected_sector_name).first()
        if not sector:
            flash('Setor inválido selecionado.', 'danger')
            return redirect(url_for('register'))
        user = User(email=request.form.get('email'), password_hash=hashed_password, is_admin=False)
        user.sectors.append(sector)
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


# --- ROTAS PRINCIPAIS DA APLICAÇÃO ---
@app.route('/')
@login_required
def dashboard():
    if not current_user.sectors:
        flash('Você não tem acesso a nenhum setor. Contate um administrador.', 'warning')
        return render_template('no_sector.html')
    first_sector_name = current_user.sectors[0].name
    return redirect(url_for('view_sector_dashboard', sector_name=first_sector_name))

@app.route('/setor/<sector_name>')
@login_required
def view_sector_dashboard(sector_name):
    all_sectors_for_dropdown = Sector.query.all()
    current_sector = Sector.query.filter_by(name=sector_name).first_or_404()
    if not current_user.is_admin and current_sector not in current_user.sectors:
        flash('Você não tem permissão para acessar este setor.', 'danger')
        return redirect(url_for('dashboard'))
    subcategories_for_sidebar = current_sector.subcategories
    active_subcategory_name = request.args.get('view', None)
    search_term = request.args.get('search', None)
    links_to_show = []
    if search_term:
        active_subcategory_name = None
        query = db.session.query(Link).join(Subcategory).join(Sector)
        if not current_user.is_admin:
            user_sector_ids = [s.id for s in current_user.sectors]
            query = query.filter(Sector.id.in_(user_sector_ids))
        links_to_show = query.filter(Link.name.ilike(f'%{search_term}%')).all()
    elif active_subcategory_name:
        for sub in subcategories_for_sidebar:
            if sub.name == active_subcategory_name:
                links_to_show = sub.links
                break
    return render_template('dashboard.html',
                           all_sectors=all_sectors_for_dropdown,
                           current_sector=current_sector,
                           subcategories=subcategories_for_sidebar,
                           active_subcategory_name=active_subcategory_name,
                           links_to_show=links_to_show,
                           search_term=search_term)

# --- COMANDOS CLI ---
@app.cli.command('create-admin')
@click.option('--email', prompt=True)
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
def create_admin_command(email, password):
    if User.query.filter_by(email=email).first():
        print(f'Erro: O e-mail {email} já existe.')
        return
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    admin = User(email=email, password_hash=hashed_password, is_admin=True)
    all_sectors = Sector.query.all()
    if not all_sectors:
        print('Aviso: Nenhum setor encontrado. O admin será criado sem setores iniciais.')
    admin.sectors.extend(all_sectors)
    db.session.add(admin)
    db.session.commit()
    print(f'Administrador {email} criado com sucesso e associado a todos os setores existentes.')

@app.cli.command('create-sector')
@click.argument('name')
def create_sector_command(name):
    """Cria um novo setor no banco de dados."""
    if Sector.query.filter_by(name=name).first():
        print(f"Erro: O setor '{name}' já existe.")
        return
    new_sector = Sector(name=name)
    db.session.add(new_sector)
    db.session.commit()
    print(f"Setor '{name}' criado com sucesso!")
    
@app.cli.command('assign-sector')
@click.argument('email')
@click.argument('sector_name')
def assign_sector_command(email, sector_name):
    """Associa um setor a um usuário existente."""
    user = User.query.filter_by(email=email).first()
    if not user:
        print(f"Erro: Usuário com e-mail '{email}' não encontrado.")
        return

    sector = Sector.query.filter_by(name=sector_name).first()
    if not sector:
        print(f"Erro: Setor com nome '{sector_name}' não encontrado.")
        return

    if sector in user.sectors:
        print(f"Aviso: O usuário '{email}' já tem acesso ao setor '{sector_name}'.")
        return

    user.sectors.append(sector)
    db.session.commit()
    print(f"Sucesso! Setor '{sector_name}' associado ao usuário '{email}'.")

@app.cli.command('populate-db')
def populate_db_command():
    """Lê um dicionário interno e popula as tabelas de setores, subcategorias e links."""
    PLANILHAS_POR_SETOR = {
        'Suporte': {
            'Documentação Técnica': { 'integracao_totvs': {'nome': 'Integração TOTVS', 'url': 'https://docs.google.com/document/d/1A_xGBWtiT8jyXCZUJMJE5sw5K3luFaS5s_A01G4v570/edit?tab=t.0'}, 'integracao_ifood': {'nome': 'Integração Ifood', 'url': 'https://docs.google.com/document/d/1q9Y4eXMrgK8vmnfjy6oIzjmcytCPl1OLs9tQ8Xi_ALU/edit?tab=t.0#heading=h.gfrmxwlev7cw'} },
            'Acompanhamento Pix': { 'pix_diario': {'nome': 'Controle PIX Diário', 'url': 'URL_AQUI'} }
        },
        'Vendas': { 'Geral': { 'vendas_q3': {'nome': 'Relatório de Vendas Q3', 'url': 'URL_AQUI'} } }
    }
    db.session.query(Link).delete()
    db.session.query(Subcategory).delete()
    db.session.query(Sector).delete()
    for sector_name, subcategories in PLANILHAS_POR_SETOR.items():
        new_sector = Sector(name=sector_name)
        db.session.add(new_sector)
        for subcategory_name, links in subcategories.items():
            new_subcategory = Subcategory(name=subcategory_name, sector=new_sector)
            db.session.add(new_subcategory)
            for link_key, link_data in links.items():
                new_link = Link(name=link_data['nome'], url=link_data['url'], subcategory=new_subcategory)
                db.session.add(new_link)
    db.session.commit()
    print('Banco de dados populado com setores e links iniciais!')