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
from flask_admin.actions import action
from markupsafe import Markup
from wtforms import StringField, IntegerField
from datetime import datetime
from flask_admin import BaseView, expose
from wtforms import validators 
from wtforms import StringField, validators
from wtforms.fields import PasswordField, TextAreaField
from wtforms.fields import BooleanField
from wtforms_sqlalchemy.fields import QuerySelectMultipleField
from flask_ckeditor import CKEditor
from flask_ckeditor import CKEditorField
import uuid
from flask import abort
from flask_ckeditor import CKEditor, CKEditorField, upload_success
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_wtf.file import FileField, FileAllowed
from werkzeug.utils import secure_filename
from flask_admin.form.widgets import Select2Widget





# --- CONFIGURAÇÃO E INICIALIZAÇÃO DA APLICAÇÃO ---
app = Flask(__name__)
ckeditor = CKEditor(app) # <-- ADICIONE ESTA LINHA
basedir = os.path.abspath(os.path.dirname(__file__))
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-dificil'
app.config['UPLOADED_PATH'] = os.path.join(basedir, 'static', 'uploads')
app.config['CKEDITOR_FILE_UPLOADER'] = 'upload' # 'upload' é o nome que daremos à nossa rota
app.config['CKEDITOR_ENABLE_CSRF'] = True

db = SQLAlchemy(app)

# --- TABELA DE ASSOCIAÇÃO ---
user_sectors_association = db.Table('user_sectors',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('sector_id', db.Integer, db.ForeignKey('sector.id'), primary_key=True)
)

post_sectors_association = db.Table('post_sectors',
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True),
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
    posts = db.relationship('Post', back_populates='author', lazy=True)

class Sector(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    order_index = db.Column(db.Integer, nullable=False, default=0) # <-- Adicionar
    subcategories = db.relationship('Subcategory', back_populates='sector', lazy=True, cascade="all, delete-orphan")
    users = db.relationship('User', secondary=user_sectors_association, lazy='subquery',
                            back_populates='sectors')
    posts = db.relationship('Post', secondary=post_sectors_association, lazy='dynamic',
                            back_populates='sectors')
    def __str__(self):
        return self.name

class Subcategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    order_index = db.Column(db.Integer, nullable=False, default=0) # <-- Adicionar
    sector_id = db.Column(db.Integer, db.ForeignKey('sector.id'), nullable=False)
    sector = db.relationship('Sector', back_populates='subcategories')
    links = db.relationship('Link', back_populates='subcategory', lazy=True, cascade="all, delete-orphan")
    
    def __str__(self):
        return self.name


class Link(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    order_index = db.Column(db.Integer, nullable=False, default=0)
    subcategory_id = db.Column(db.Integer, db.ForeignKey('subcategory.id'), nullable=False)
    subcategory = db.relationship('Subcategory', back_populates='links')
    
    def __str__(self):
        return self.name

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_filename = db.Column(db.String(100), nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    order_index = db.Column(db.Integer, nullable=False, default=0)
    
    # A nova relação "muitos-para-muitos" com Setores
    sectors = db.relationship('Sector', secondary=post_sectors_association, lazy='subquery',
                              back_populates='posts')
    
    # A relação com o autor continua a mesma
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    author = db.relationship('User', back_populates='posts')
    
    def __repr__(self):
        return f'<Post {self.title}>'

# --- CONFIGURAÇÃO DO PAINEL ADMIN ---
class SecureModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.is_admin
    def inaccessible_callback(self, name, **kwargs):
        flash('Você precisa ser um administrador para acessar esta página.', 'danger')
        return redirect(url_for('login'))

# Substitua sua UserAdminView atual por esta versão
class UserAdminView(SecureModelView):
    # Colunas que aparecem na TELA DE LISTAGEM
    column_list = ['email', 'is_admin', 'sectors']
    
    # EXCLUI o campo 'password_hash' do formulário para evitar conflitos
    form_excluded_columns = ['password_hash']

    # Adiciona nosso campo de senha temporário ao formulário
    form_extra_fields = {
        'password': PasswordField('Nova Senha [Deixe em branco para não alterar]')
    }

    # Intercepta o processo de salvar para criptografar a senha (versão segura)
    def on_model_change(self, form, model, is_created):
        if form.password.data:
            model.password_hash = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        elif is_created and not form.password.data:
            raise validators.ValidationError('O campo "Nova Senha" é obrigatório ao criar um novo usuário.')
        
class UserForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Nova Senha [Deixe em branco para não alterar]')
    is_admin = BooleanField('É Administrador?')
    sectors = QuerySelectMultipleField(
        label='Setores',
        query_factory=lambda: Sector.query.all(),
        get_label='name',
        allow_blank=True
    )

class PostForm(FlaskForm):
    sectors = QuerySelectMultipleField(
        label='Setores',
        query_factory=lambda: Sector.query.all(),
        get_label='name',
        validators=[DataRequired()],
        widget=Select2Widget(multiple=True),
        render_kw={'class': 'form-control'} # <-- ADICIONE APENAS ESTA LINHA
    )
    title = StringField('Título', validators=[DataRequired()])
    content = TextAreaField('Conteúdo', render_kw={'class': 'ckeditor'})
    image = FileField('Imagem de Destaque', validators=[
        FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Apenas imagens são permitidas!')
    ])
    order_index = IntegerField('Ordem', default=0)



class PostAdminView(SecureModelView):
    # Usa nosso formulário customizado atualizado
    form = PostForm

    # Garante que o script do CKEditor seja carregado
    extra_js = ['//cdn.ckeditor.com/4.22.1/full/ckeditor.js']

    form_widget_args = {
        'sectors': {
            'class': 'select2'
        }
    }

    # Colunas que serão exibidas na lista (com 'sectors' no plural)
    column_list = ['title', 'author', 'sectors', 'timestamp', 'order_index']

    # Filtros (com 'sectors' no plural)
    column_filters = ['sectors', 'author']

    # Ordenação padrão da lista
    column_default_sort = ('timestamp', True)

    # Edição rápida na lista
    column_editable_list = ['title', 'order_index']

    # Método para salvar o modelo
    def on_model_change(self, form, model, is_created):
        if is_created:
            model.author_id = current_user.id

        if form.image.data:
            file = form.image.data
            filename = secure_filename(str(uuid.uuid4()) + os.path.splitext(file.filename)[1])
            file.save(os.path.join(app.config['UPLOADED_PATH'], filename))
            model.image_filename = filename



# --- FIM DO BLOCO PARA COPIAR ---

class SectorAdminView(SecureModelView):
    can_create = True
    column_list = ['name', 'subcategories']
    column_searchable_list = ['name']

    # Adicione esta linha para limitar o formulário
    form_columns = ['name']


class SubcategoryAdminView(SecureModelView):
    # Aponta para o nosso novo template customizado
    list_template = 'admin/subcategory_list.html'

    # Define a ordenação padrão pela nossa nova coluna
    column_default_sort = ('order_index', False)

    # Renomeia o cabeçalho da coluna para algo mais amigável
    column_labels = {'order_index': 'Ordem'}

    # Função para criar o ícone de arrastar (a "alça")
    def _order_formatter(view, context, model, name):
        return Markup(f'<div class="drag-handle" style="cursor: move; text-align: center;" data-id="{model.id}">&#9776;</div>')

    # Associa nossa função à coluna 'order_index'
    column_formatters = {
        'order_index': _order_formatter
    }

    # Define as colunas que serão exibidas na lista
    column_list = ['order_index', 'name', 'sector']
    
    # Campos que aparecerão no formulário de criação/edição
    form_columns = ['name', 'sector', 'order_index']
    
    # Mantém a busca e os filtros
    column_searchable_list = ['name']
    column_filters = ['sector']


@app.route('/api/subcategories/<int:sector_id>')
@login_required
def api_subcategories(sector_id):
    subcategories = Subcategory.query.filter_by(sector_id=sector_id).all()
    
    # Transforma a lista de objetos em um formato que o JavaScript entende (JSON)
    subcat_list = [{'id': sub.id, 'name': sub.name} for sub in subcategories]
    
    return jsonify(subcat_list)

# --- ROTA PARA UPLOAD DE IMAGENS DO CKEDITOR ---
@app.route('/upload', methods=['POST'])
@login_required
def upload():
    # Garante que apenas administradores possam fazer upload
    if not current_user.is_admin:
        abort(403)

    # Pega o arquivo enviado pelo CKEditor
    f = request.files.get('upload')
    if f is None:
        return jsonify({'error': {'message': 'Nenhum arquivo enviado.'}}), 400

    # Gera um nome de arquivo seguro e único
    extension = os.path.splitext(f.filename)[1].lower()
    if extension not in ['.jpg', '.gif', '.png', '.jpeg']:
        return jsonify({'error': {'message': 'Tipo de arquivo de imagem inválido.'}}), 400
        
    filename = str(uuid.uuid4()) + extension
    
    # Salva o arquivo na nossa pasta de uploads
    f.save(os.path.join(app.config['UPLOADED_PATH'], filename))
    
    # Gera a URL pública para a imagem
    url = url_for('static', filename=f'uploads/{filename}')
    
    # Retorna a resposta JSON no formato que o CKEditor espera
    return jsonify({'uploaded': 1, 'fileName': filename, 'url': url})

# Ação de reset de senha
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

@app.route('/api/links/reorder', methods=['POST'])
@login_required
def reorder_links():
    if not current_user.is_admin:
        return jsonify({'status': 'error', 'message': 'Permission denied'}), 403

    ordered_ids = request.get_json().get('ordered_ids')

    if not ordered_ids:
        return jsonify({'status': 'error', 'message': 'No data received'}), 400

    try:
        for index, link_id in enumerate(ordered_ids):
            link = db.session.get(Link, int(link_id))
            if link:
                link.order_index = index
        
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Ordem dos links atualizada.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
# Adicione esta nova rota para salvar a ordem das subcategorias
@app.route('/api/subcategories/reorder', methods=['POST'])
@login_required
def reorder_subcategories():
    if not current_user.is_admin:
        return jsonify({'status': 'error', 'message': 'Permission denied'}), 403

    ordered_ids = request.get_json().get('ordered_ids')

    if not ordered_ids:
        return jsonify({'status': 'error', 'message': 'No data received'}), 400

    try:
        for index, subcategory_id in enumerate(ordered_ids):
            subcategory = db.session.get(Subcategory, int(subcategory_id))
            if subcategory:
                subcategory.order_index = index
        
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Ordem das subcategorias atualizada.'})
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


class LinkAdminView(SecureModelView):
    # Usa nosso formulário customizado
    form = LinkForm
    
    # Aponta para os templates de criação/edição/lista
    create_template = 'admin/link_create.html'
    edit_template = 'admin/link_edit.html'
    list_template = 'admin/link_list.html'
    
    # Ordenação padrão da lista
    column_default_sort = ('order_index', False)

    # NOVO: Define um nome amigável para a coluna. Esta é a forma correta.
    column_labels = {'order_index': 'Ordem'}

    # Função para criar o HTML do ícone de arrastar
    def _order_formatter(view, context, model, name):
        # O ícone 'hamburger' (☰) serve como a alça visual
        return Markup(f'<div class="drag-handle" style="cursor: move; text-align: center;" data-id="{model.id}">&#9776;</div>')

    # Diz ao Admin para usar nossa função para formatar a coluna 'order_index'
    column_formatters = {
        'order_index': _order_formatter
    }

    # AJUSTADO: Usa o nome simples da coluna na lista
    column_list = ['order_index', 'name', 'url', 'subcategory']
    
    # Especifica quais campos aparecem no formulário de edição/criação
    form_columns = ['sector', 'order_index', 'name', 'url', 'subcategory']

    # Adiciona um painel de filtros na lateral da lista
    column_filters = [
        # Filtro baseado no relacionamento com Subcategoria e depois com Setor
        'subcategory.sector', 
        
        # Filtro baseado diretamente no relacionamento com Subcategoria
        'subcategory'
    ]
    # --- FIM DO BLOCO ---

    form_columns = ['sector', 'order_index', 'name', 'url', 'subcategory']

admin = Admin(app, name='Painel de Controle', template_mode='bootstrap4',
              base_template='admin/custom_base.html')

admin.add_view(UserAdminView(User, db.session, name='Usuários'))
admin.add_view(SectorAdminView(Sector, db.session, name='Setores'))
admin.add_view(SubcategoryAdminView(Subcategory, db.session, name='Subcategorias'))
admin.add_view(LinkAdminView(Link, db.session, name='Links'))
admin.add_view(PostAdminView(Post, db.session, name='Notícias'))
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

# Adicione esta nova rota
@app.route('/setor/<string:sector_name>/home')
@login_required
def view_sector_home(sector_name):
    # Encontra o setor pelo nome ou retorna erro 404
    sector = Sector.query.filter_by(name=sector_name).first_or_404()

    # Validação de segurança para garantir que o usuário tem acesso a este setor
    if not current_user.is_admin and sector not in current_user.sectors:
        flash('Você não tem permissão para acessar este setor.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Busca todas as postagens daquele setor, ordenadas pela data (mais nova primeiro)
    posts = sector.posts.order_by(Post.timestamp.desc()).all()

    return render_template('sector_home.html', current_sector=sector, posts=posts)

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
    
    subcategories_for_sidebar = Subcategory.query.filter_by(sector_id=current_sector.id).order_by(Subcategory.order_index).all()
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