import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt

# --- MAPA DE PLANILHAS COM SUBCATEGORIAS ---
# Estrutura: Setor -> Subcategoria -> Planilha
PLANILHAS_POR_SETOR = {
    'Suporte': {
        'Documentação Técnica': {
            'integracao_totvs': {
                'nome': 'Integração TOTVS',
                'url': 'https://docs.google.com/document/d/1A_xGBWtiT8jyXCZUJMJE5sw5K3luFaS5s_A01G4v570/edit?tab=t.0'
            },
            'teste': {
                'nome': 'teste novo',
                'url': 'https://discord.com/channels/689989595617820716/1390364328309424288/1390373488476295280'
            }
        },
        'Acompanhamento Pix': {
            'acompanhamento pix': {
                'nome': 'Acompanhamento Pix',
                'url': 'https://docs.google.com/spreadsheets/d/1c_ANia5o319L314nt24TpRqBIlr7V6ps7omL6sGqK8U/edit?gid=726468821#gid=726468821'
            }
        }
    },
    'Vendas': {
        'Geral': {
            'vendas_q3': {
                'nome': 'Relatório de Vendas Q3',
                'url': 'URL_DA_SUA_PLANILHA_DE_VENDAS_AQUI'
            },
            'metas_vendedores': {
                'nome': 'Metas por Vendedor',
                'url': 'URL_DA_SUA_OUTRA_PLANILHA_DE_VENDAS_AQUI'
            }
        }
    },
    'CS': {
        'Geral': {
            'health_score': {
                'nome': 'Health Score Clientes',
                'url': 'URL_DA_SUA_PLANILHA_DE_CS_AQUI'
            }
        }
    }
}


# --- CONFIGURAÇÃO INICIAL DA APLICAÇÃO ---
app = Flask(__name__)
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


# --- MODELO DE USUÁRIO (BANCO DE DADOS) ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(60), nullable=False)
    sector = db.Column(db.String(50), nullable=False)


# --- ROTAS DE AUTENTICAÇÃO ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and bcrypt.check_password_hash(user.password_hash, request.form.get('password')):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Login sem sucesso. Por favor, verifique o e-mail e a senha.', 'danger')
    return render_template('login.html', title='Login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_password = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')
        user = User(
            email=request.form.get('email'),
            password_hash=hashed_password,
            sector=request.form.get('sector')
        )
        db.session.add(user)
        db.session.commit()
        flash('Sua conta foi criada! Você já pode fazer login.', 'success')
        return redirect(url_for('login'))
    # Passa apenas os nomes dos setores para o template de registro
    return render_template('register.html', title='Registrar', sectors=PLANILHAS_POR_SETOR.keys())

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


# --- NOVAS ROTAS DE NAVEGAÇÃO (SIMPLIFICADO) ---
@app.route('/')
@login_required
def index():
    """Redireciona o usuário logado para a página do seu setor."""
    user_sector = current_user.sector
    return redirect(url_for('view_sector', sector_name=user_sector))

@app.route('/setor/<sector_name>')
@login_required
def view_sector(sector_name):
    """Mostra a página de um setor com os menus suspensos para cada subcategoria."""
    if sector_name != current_user.sector:
        flash('Você não tem permissão para acessar este setor.', 'danger')
        return redirect(url_for('view_sector', sector_name=current_user.sector))
    
    # Pega todos os dados do setor (incluindo subcategorias e planilhas)
    sector_data = PLANILHAS_POR_SETOR.get(sector_name, {})
    
    # Envia o dicionário completo para o template
    return render_template('sector_page.html', sector_name=sector_name, subcategories=sector_data)

# A ROTA view_subcategory FOI REMOVIDA

@app.route('/setor/<sector_name>/<subcategory_name>')
@login_required
def view_subcategory(subcategory_name, sector_name):
    """Mostra os links finais de uma subcategoria."""
    if sector_name != current_user.sector:
        flash('Você não tem permissão para acessar este setor.', 'danger')
        return redirect(url_for('view_sector', sector_name=current_user.sector))
        
    sector_data = PLANILHAS_POR_SETOR.get(sector_name, {})
    planilhas_data = sector_data.get(subcategory_name, {})
    
    return render_template('subcategory_page.html', 
                           sector_name=sector_name, 
                           subcategory_name=subcategory_name, 
                           planilhas=planilhas_data)

# --- EXECUÇÃO DA APLICAÇÃO ---
if __name__ == '__main__':
    app.run(debug=True)