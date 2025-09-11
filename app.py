import os
import click
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_admin.menu import MenuLink
from wtforms_sqlalchemy.fields import QuerySelectField
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField
from wtforms.validators import DataRequired
from wtforms.fields import PasswordField
from flask_admin.actions import action
from markupsafe import Markup
from wtforms import StringField, IntegerField


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
    order_index = db.Column(db.Integer, nullable=False, default=0) # <-- ADICIONE ESTA LINHA
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

# VERSÃO CORRIGIDA da UserAdminView
# Não se esqueça do import no topo do arquivo, caso ele não esteja lá
# from wtforms.fields import PasswordField

# --- COLE ESTE BLOCO CORRIGIDO NO LUGAR DA SUA UserAdminView ATUAL ---

class UserAdminView(SecureModelView):
    # Colunas que aparecem na TELA DE LISTAGEM
    column_list = ['email', 'is_admin', 'sectors']
    
    # EXCLUI o campo 'password_hash' do formulário para evitar conflitos
    form_excluded_columns = ['password_hash']

    # Adiciona nosso campo de senha temporário ao formulário de criação/edição
    form_extra_fields = {
        'password': PasswordField('Nova Senha [Deixe em branco para não alterar]')
    }

    # Intercepta o processo de salvar para criptografar a senha corretamente
    def on_model_change(self, form, model, is_created):
        # Se o campo de senha foi preenchido, nós geramos o hash
        if form.password.data:
            model.password_hash = bcrypt.generate_password_hash(form.password.data).decode('utf-8')

    # Cria a ação customizada para resetar a senha
    @action('reset_password', 
            'Resetar Senha para Padrão', 
            'Tem certeza que deseja resetar a senha destes usuários para "12345"?')
    def reset_password(self, ids):
        try:
            query = User.query.filter(User.id.in_(ids))
            
            default_password_hash = bcrypt.generate_password_hash('12345').decode('utf-8')
            
            count = 0
            for user in query.all():
                user.password_hash = default_password_hash
                count += 1
            
            db.session.commit()
            
            flash(f'{count} senha(s) de usuário(s) foi(ram) resetada(s) para o padrão "12345".', 'success')
        except Exception as ex:
            flash(f'Falha ao resetar senhas: {str(ex)}', 'danger')

# --- FIM DO BLOCO PARA COPIAR ---

class SectorAdminView(SecureModelView):
    can_create = True
    column_list = ['name', 'subcategories']
    column_searchable_list = ['name']

    # Adicione esta linha para limitar o formulário
    form_columns = ['name']

class SubcategoryAdminView(SecureModelView):
    form_columns = ['name', 'sector']
#    form_ajax_refs = { 'sector': { 'fields': ['name'] } }
    column_searchable_list = ['name']

@app.route('/api/subcategories/<int:sector_id>')
@login_required
def api_subcategories(sector_id):
    subcategories = Subcategory.query.filter_by(sector_id=sector_id).all()
    
    # Transforma a lista de objetos em um formato que o JavaScript entende (JSON)
    subcat_list = [{'id': sub.id, 'name': sub.name} for sub in subcategories]
    
    return jsonify(subcat_list)

@app.route('/api/links/reorder', methods=['POST'])
@login_required
def reorder_links():
    # Garante que apenas administradores possam reordenar
    if not current_user.is_admin:
        return jsonify({'status': 'error', 'message': 'Permission denied'}), 403

    # Pega a lista de IDs na nova ordem enviada pelo JavaScript
    ordered_ids = request.get_json().get('ordered_ids')

    if not ordered_ids:
        return jsonify({'status': 'error', 'message': 'No data received'}), 400

    try:
        # Atualiza o order_index de cada link baseado na sua posição na lista
        for index, link_id in enumerate(ordered_ids):
            link = db.session.get(Link, int(link_id))
            if link:
                link.order_index = index
        
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Ordem dos links atualizada.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- ANTES da classe LinkAdminView ---
class LinkForm(FlaskForm):
    sector = QuerySelectField(
        label='Setor',
        query_factory=lambda: Sector.query.all(),
        get_label='name',
        allow_blank=True,
        blank_text='-- Selecione um Setor --'
    )
    # A linha 'order_index' foi removida.
    name = StringField('Nome do Link', validators=[DataRequired()])
    url = StringField('URL', validators=[DataRequired()])
    subcategory = QuerySelectField(
        label='Subcategoria',
        query_factory=lambda: Subcategory.query.all(),
        get_label='name',
        allow_blank=True,
        blank_text='-- Selecione um Setor primeiro --'
    )


# NO SEU app.py
class LinkAdminView(SecureModelView):
    # Usa nosso formulário customizado
    form = LinkForm

    # Aponta para os templates de criação/edição que já funcionam
    create_template = 'admin/link_create.html'
    edit_template = 'admin/link_edit.html'

    # Define as colunas que aparecem na lista
    column_list = ['order_index', 'name', 'url', 'subcategory']

    # Define a ordenação padrão da lista
    column_default_sort = ('order_index', False) # False = menor para o maior

    # Torna a coluna 'order_index' editável diretamente na tela de lista
    column_editable_list = ['order_index']
    form_columns = ['sector', 'name', 'url', 'subcategory', 'order_index']

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

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not new_password or not confirm_password:
            flash('Por favor, preencha ambos os campos.', 'warning')
            return redirect(url_for('change_password'))

        if new_password != confirm_password:
            flash('As senhas não coincidem. Tente novamente.', 'danger')
            return redirect(url_for('change_password'))
        
        # Se tudo estiver certo, atualiza a senha
        user = current_user
        user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
        db.session.commit()

        flash('Sua senha foi alterada com sucesso!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('change_password.html', title='Alterar Senha')


# --- ROTAS PRINCIPAIS DA APLICAÇÃO ---
@app.route('/')
@login_required
def dashboard():
    if not current_user.sectors:
        flash('Você não tem acesso a nenhum setor. Contate um administrador.', 'warning')
        return render_template('no_sector.html')
    first_sector_name = current_user.sectors[0].name
    return redirect(url_for('view_sector_dashboard', sector_name=first_sector_name))

# NO SEU app.py
@app.route('/setor/<sector_name>')
@login_required
def view_sector_dashboard(sector_name):
    # ... (o início da sua função está correto e não muda)
    sectors_for_dropdown = Sector.query.all() if current_user.is_admin else current_user.sectors
    current_sector = Sector.query.filter_by(name=sector_name).first_or_404()
    if not current_user.is_admin and current_sector not in current_user.sectors:
        flash('Você não tem permissão para acessar este setor.', 'danger')
        return redirect(url_for('dashboard'))
    
    subcategories_for_sidebar = Subcategory.query.filter_by(sector_id=current_sector.id).all()
    active_subcategory_name = request.args.get('view', None)
    search_term = request.args.get('search', None)
    links_to_show = []

    # Query base para links dentro do setor atual
    query = db.session.query(Link).join(Subcategory).filter(Subcategory.sector_id == current_sector.id)

    if search_term:
        active_subcategory_name = None
        # Adiciona a busca à query base e ordena
        links_to_show = query.filter(Link.name.ilike(f'%{search_term}%')).order_by(Link.order_index).all()
    elif active_subcategory_name:
        # Adiciona o filtro de subcategoria à query base e ordena
        links_to_show = query.filter(Subcategory.name == active_subcategory_name).order_by(Link.order_index).all()
    else:
        # Mostra todos os links do setor, ordenados
        links_to_show = query.order_by(Link.order_index).all()
    
    return render_template('dashboard.html',
                           sectors_for_dropdown=sectors_for_dropdown,
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
    pass # Desativado