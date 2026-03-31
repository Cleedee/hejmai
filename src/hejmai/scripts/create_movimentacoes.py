import sqlite3
import os

# Caminho para o seu banco no volume Docker ou local
DB_PATH = os.getenv("DATABASE_PATH", "./estoque.db")

def criar_tabela_movimentacoes():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"🚀 A iniciar migração no banco: {DB_PATH}")

    try:
        # Criar a tabela de Movimentações
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS movimentacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto_id INTEGER NOT NULL,
                quantidade REAL NOT NULL,
                tipo TEXT NOT NULL,
                data_movimento DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (produto_id) REFERENCES produtos (id)
            )
        ''')
        
        # Opcional: Criar um index para acelerar as projeções de consumo
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mov_produto_data ON movimentacoes (produto_id, data_movimento)')
        
        conn.commit()
        print("✅ Tabela 'movimentacoes' criada com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro na migração: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    criar_tabela_movimentacoes()
