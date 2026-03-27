
class SanityChecker:
    @staticmethod
    def validar_item(item: dict):
        alertas = []
        
        # 1. Check de Preço Absurdo (Preços unitários fora do comum)
        preco_unitario = item['preco_pago'] / item['quantidade'] if item['quantidade'] > 0 else 0
        
        # Exemplos de limites para o mercado brasileiro em 2026
        if preco_unitario > 300: 
            alertas.append(f"Preço unitário de {item['nome']} parece muito alto (R$ {preco_unitario:.2f}).")
        
        if item['preco_pago'] <= 0:
            alertas.append(f"O item {item['nome']} está com preço zero ou negativo.")

        # 2. Check de Quantidade (Evitar erros de digitação/OCR)
        if item['quantidade'] > 50 and item['unidade'] in ['kg', 'l']:
            alertas.append(f"Quantidade de {item['nome']} ({item['quantidade']}{item['unidade']}) parece excessiva.")

        return alertas
