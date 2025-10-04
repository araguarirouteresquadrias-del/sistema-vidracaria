import os
import psycopg2
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime
import logging

app = Flask(__name__)
app.secret_key = 'vidracaria_mobile_2024_seguranca'

# Configuração do PostgreSQL para Railway
def get_db_connection():
    try:
        conn = psycopg2.connect(os.environ['DATABASE_URL'])
        return conn
    except Exception as e:
        logging.error(f"Erro de conexão: {e}")
        return None

# Criar tabelas se não existirem
def criar_tabelas():
    conn = get_db_connection()
    if not conn:
        return
        
    try:
        cur = conn.cursor()
        
        # Tabela de produtos
        cur.execute('''
            CREATE TABLE IF NOT EXISTS produtos (
                id SERIAL PRIMARY KEY,
                codigo TEXT,
                nome TEXT NOT NULL UNIQUE,
                descricao TEXT,
                tipo TEXT,
                espessura REAL,
                unidade_medida TEXT
            )
        ''')
        
        # Tabela de cores
        cur.execute('''
            CREATE TABLE IF NOT EXISTS cores (
                id SERIAL PRIMARY KEY,
                nome TEXT NOT NULL UNIQUE
            )
        ''')
        
        # Tabela de estoque
        cur.execute('''
            CREATE TABLE IF NOT EXISTS estoque (
                id SERIAL PRIMARY KEY,
                produto_id INTEGER REFERENCES produtos(id),
                cor_id INTEGER REFERENCES cores(id),
                quantidade REAL,
                data_atualizacao DATE,
                UNIQUE(produto_id, cor_id)
            )
        ''')
        
        # Tabela de vendas
        cur.execute('''
            CREATE TABLE IF NOT EXISTS vendas (
                id SERIAL PRIMARY KEY,
                produto_id INTEGER REFERENCES produtos(id),
                cor_id INTEGER REFERENCES cores(id),
                quantidade REAL,
                data_venda DATE,
                descricao TEXT
            )
        ''')
        
        # Inserir cores padrão
        cur.execute("INSERT INTO cores (nome) VALUES ('Natural') ON CONFLICT DO NOTHING")
        cur.execute("INSERT INTO cores (nome) VALUES ('Branco') ON CONFLICT DO NOTHING") 
        cur.execute("INSERT INTO cores (nome) VALUES ('Preto') ON CONFLICT DO NOTHING")
        
        conn.commit()
        cur.close()
        print("✅ Tabelas criadas com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro ao criar tabelas: {e}")
    finally:
        conn.close()

# Rotas da aplicação
@app.route('/')
def index():
    if 'logado' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        senha = request.form.get('senha')
        if senha == '203060':
            session['logado'] = True
            return redirect(url_for('index'))
        return "Senha incorreta! Tente novamente."
    return render_template('login.html')

@app.route('/api/estoque')
def api_estoque():
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Erro de conexão'}), 500
        
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT e.id, p.codigo, p.nome, c.nome as cor, 
                   e.quantidade, p.unidade_medida, e.data_atualizacao
            FROM estoque e
            JOIN produtos p ON e.produto_id = p.id
            JOIN cores c ON e.cor_id = c.id
            ORDER BY p.nome
        ''')
        
        estoque = cur.fetchall()
        cur.close()
        
        # Converter para dicionário
        resultado = []
        for item in estoque:
            resultado.append({
                'id': item[0],
                'codigo': item[1],
                'nome': item[2],
                'cor': item[3],
                'quantidade': float(item[4]) if item[4] else 0,
                'unidade_medida': item[5],
                'data_atualizacao': item[6].strftime('%d/%m/%Y') if item[6] else ''
            })
            
        return jsonify(resultado)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/vender', methods=['POST'])
def api_vender():
    data = request.json
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Erro de conexão'})
    
    try:
        cur = conn.cursor()
        
        # Verificar estoque
        cur.execute('SELECT quantidade, produto_id, cor_id FROM estoque WHERE id = %s', (data['item_id'],))
        estoque_atual = cur.fetchone()
        
        if not estoque_atual:
            return jsonify({'success': False, 'error': 'Item não encontrado'})
            
        if estoque_atual[0] < data['quantidade']:
            return jsonify({'success': False, 'error': 'Estoque insuficiente!'})
        
        # Registrar venda
        cur.execute('''
            INSERT INTO vendas (produto_id, cor_id, quantidade, data_venda, descricao)
            VALUES (%s, %s, %s, %s, %s)
        ''', (estoque_atual[1], estoque_atual[2], data['quantidade'],
              datetime.now().strftime('%Y-%m-%d'), data['descricao']))
        
        # Atualizar estoque
        cur.execute('''
            UPDATE estoque SET quantidade = quantidade - %s, data_atualizacao = %s
            WHERE id = %s
        ''', (data['quantidade'], datetime.now().strftime('%Y-%m-%d'), data['item_id']))
        
        conn.commit()
        cur.close()
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        conn.close()

@app.route('/api/produtos')
def api_produtos():
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Erro de conexão'}), 500
        
    try:
        cur = conn.cursor()
        cur.execute('SELECT id, codigo, nome, tipo, unidade_medida FROM produtos ORDER BY nome')
        produtos = cur.fetchall()
        cur.close()
        
        resultado = []
        for p in produtos:
            resultado.append({
                'id': p[0],
                'codigo': p[1],
                'nome': p[2],
                'tipo': p[3],
                'unidade_medida': p[4]
            })
            
        return jsonify(resultado)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Inicializar tabelas ao iniciar
if __name__ == '__main__':
    criar_tabelas()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
