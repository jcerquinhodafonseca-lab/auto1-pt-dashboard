# Auto1 PT — Dashboard AM

Dashboard para Account Managers da Auto1 Portugal. Permite pesquisar carros disponíveis na plataforma, calcular margens de compra e gerar mensagens automáticas para WhatsApp.

## Funcionalidades

- **Catálogo PT em tempo real** — todos os carros disponíveis (status 6) diretamente do Redash
- **Pesquisa por número de stock** (ex: HA23712) com dados completos
- **Filtros** por marca, combustível, condição
- **Calculadora de margem** — PVP Ideal, custos de serviço, transporte, obra, margem bruta → preço ideal de compra
- **Geração automática de mensagem** no formato padrão Auto1
- **Envio direto para WhatsApp Web** com texto pré-preenchido
- **Histórico** de recomendações por cliente

## Como correr (versão standalone — recomendado)

Não precisa instalar nada além de Python 3:

```bash
python dashboard.py
```

O browser abre automaticamente em `http://localhost:5000`.  
Na primeira execução demora ~15 segundos a carregar o catálogo.

## Como correr (versão Flask — desenvolvimento)

```bash
pip install flask requests
python app.py
```

## Ficheiros

| Ficheiro | Descrição |
|---|---|
| `dashboard.py` | Aplicação standalone — **usar este** |
| `app.py` | Versão Flask (para desenvolvimento) |
| `static/index.html` | Frontend da versão Flask |
| `recommendations.db` | Base de dados local (criada automaticamente) |

## Exemplo de mensagem gerada

```
Volvo V40 Cross Country - 2015 - 139.794 km - Não acidentado - Nacional

€ 14.950 (PVP ideal) - € 418 (Custos de serviço) - € 99 (Transporte) - € 750 (Obra) - € 3.000 (Margem bruta) = € 10.683 (Preço ideal de compra)
O nosso está €1.375 mais barato, o que incrementa à margem bruta

🔗 https://www.auto1.com/pt/app/merchant/car/HA23712
```
