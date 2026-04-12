#!/usr/bin/env python
"""
Script para sugerir e aplicar tags aos produtos.

Uso:
    python scripts/atualizar_tags.py          # Ver sugestões
    python scripts/atualizar_tags.py --apply  # Aplicar ao banco
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from hejmai.database import SessionLocal
from hejmai import models


CATEGORIA_TAGS = {
    'Mercearia': ['mercearia'],
    'Laticínio': ['laticinio', 'leite'],
    'Açougue': ['carne', 'proteina'],
    'Hortifruti': ['fruta', 'verdura', 'legume'],
    'Padaria': ['pao', 'farinaceo'],
    'Bebidas': ['bebida'],
    'Limpeza': ['limpeza'],
    'Higiene': ['higiene'],
}

STOP_WORDS = {'de', 'da', 'do', 'em', 'com', 'sem', 'e', 'ou', 'para'}


def extrair_tags(nome: str, categoria: str) -> str:
    """Extrai tags de um produto baseado no nome e categoria."""
    tags = []
    nome_lower = nome.lower()
    
    if categoria in CATEGORIA_TAGS:
        tags.extend(CATEGORIA_TAGS[categoria])
    
    palavras = nome_lower.replace('-', ' ').replace('/', ' ').split()
    for palavra in palavras:
        if len(palavra) > 2 and palavra not in STOP_WORDS:
            tag = ''.join(c for c in palavra if c.isalnum())
            if tag and tag not in STOP_WORDS:
                tags.append(tag)
    
    return ','.join(sorted(set(tags)))


def mostrar_sugestoes(db):
    """Mostra as sugestões de tags sem aplicar."""
    produtos = db.query(models.Produto).all()
    
    print('=== Sugestões de Tags ===\n')
    
    atualizados = 0
    total = 0
    
    for p in produtos:
        tags_atual = p.tags or ''
        tags_sugeridas = extrair_tags(p.nome, p.categoria or '')
        
        if tags_atual:
            status = '✓ (mantém)'
        else:
            status = '← NOVO'
            atualizados += 1
        
        total += 1
        print(f"{p.id:2}. {p.nome[:25]:<25} [{p.categoria[:10]:<10}] {tags_atual or '-':<25} → {tags_sugeridas} {status}")
    
    print(f'\n{total} produtos | {atualizados} sem tags (serão atualizados)')


def aplicar_tags(db, dry_run=True):
    """Aplica as tags sugeridas aos produtos sem tags."""
    produtos = db.query(models.Produto).all()
    
    atualizados = 0
    
    for p in produtos:
        if not p.tags:
            nova_tag = extrair_tags(p.nome, p.categoria or '')
            if dry_run:
                print(f'[DRY-RUN] {p.nome}: {nova_tag}')
            else:
                p.tags = nova_tag
                print(f'✓ {p.nome}: {nova_tag}')
            atualizados += 1
    
    if not dry_run:
        db.commit()
        print(f'\n✅ {atualizados} produtos atualizados com tags!')
    else:
        print(f'\n[DRY-RUN] {atualizados} produtos seriam atualizados')
    
    return atualizados


def main():
    parser = argparse.ArgumentParser(description='Sugerir/aplicar tags aos produtos')
    parser.add_argument('--apply', action='store_true', help='Aplicar tags ao banco (sem isso, apenas mostra sugestões)')
    parser.add_argument('--dry-run', action='store_true', help='Mostrar o que seria feito sem aplicar')
    args = parser.parse_args()
    
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///./data/estoque.db')
    os.environ['DATABASE_URL'] = db_url
    
    db = SessionLocal()
    try:
        if args.apply and not args.dry_run:
            aplicar_tags(db, dry_run=False)
        elif args.dry_run:
            aplicar_tags(db, dry_run=True)
        else:
            mostrar_sugestoes(db)
            print('\n💡 Use --apply para aplicar as tags ao banco')
    finally:
        db.close()


if __name__ == '__main__':
    main()
