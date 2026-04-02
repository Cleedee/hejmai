"""
Migração: Adicionar colunas de exclusão lógica na tabela compras

Adiciona:
- excluida (INTEGER, default 0)
- data_exclusao (DATETIME, nullable)
"""

import sqlite3
import os

DB_PATH = os.getenv("DATABASE_PATH", "./data/estoque.db")


def adicionar_colunas_exclusao_logica():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"🚀 Iniciando migração no banco: {DB_PATH}")

    try:
        # Verifica se as colunas já existem
        cursor.execute("PRAGMA table_info(compras)")
        colunas = [col[1] for col in cursor.fetchall()]

        # Adiciona coluna 'excluida' se não existir
        if "excluida" not in colunas:
            cursor.execute(
                """
                ALTER TABLE compras
                ADD COLUMN excluida INTEGER DEFAULT 0
                """
            )
            print("✅ Coluna 'excluida' adicionada com sucesso!")
        else:
            print("ℹ️  Coluna 'excluida' já existe.")

        # Adiciona coluna 'data_exclusao' se não existir
        if "data_exclusao" not in colunas:
            cursor.execute(
                """
                ALTER TABLE compras
                ADD COLUMN data_exclusao DATETIME
                """
            )
            print("✅ Coluna 'data_exclusao' adicionada com sucesso!")
        else:
            print("ℹ️  Coluna 'data_exclusao' já existe.")

        conn.commit()
        print("✅ Migração concluída com sucesso!")

    except Exception as e:
        print(f"❌ Erro na migração: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    adicionar_colunas_exclusao_logica()
