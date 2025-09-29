import pandas as pd
import sqlite3
from datetime import datetime
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

class FinanceSystem:
    def __init__(self, db_path="finance.db"):
        self.db_path = db_path
        self.setup_database()
    
    def setup_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabela de produtos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                print_time REAL NOT NULL,
                filament_weight REAL NOT NULL,
                sale_price REAL NOT NULL
            )
        """)
        
        # Tabela de vendas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY,
                product_id INTEGER,
                quantity INTEGER,
                sale_price REAL,
                filament_cost REAL,
                energy_cost REAL,
                date DATE,
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        """)
        
        # Configurações básicas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value REAL
            )
        """)
        
        # Valores padrão
        cursor.execute("INSERT OR IGNORE INTO settings VALUES ('kwh_price', 0.80)")
        cursor.execute("INSERT OR IGNORE INTO settings VALUES ('printer_power', 200)")
        cursor.execute("INSERT OR IGNORE INTO settings VALUES ('filament_price_kg', 80.0)")
        
        conn.commit()
        conn.close()
    
    def add_product(self, name, print_time, filament_weight, sale_price):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO products VALUES (NULL, ?, ?, ?, ?)", 
                      (name, print_time, filament_weight, sale_price))
        conn.commit()
        conn.close()
    
    def add_sale(self, product_id, quantity=1):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Buscar dados do produto
        cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        product = cursor.fetchone()
        
        # Buscar configurações
        cursor.execute("SELECT value FROM settings WHERE key = 'kwh_price'")
        kwh_price = cursor.fetchone()[0]
        cursor.execute("SELECT value FROM settings WHERE key = 'printer_power'")
        printer_power = cursor.fetchone()[0]
        cursor.execute("SELECT value FROM settings WHERE key = 'filament_price_kg'")
        filament_price_kg = cursor.fetchone()[0]
        
        # Calcular custos
        energy_cost = (printer_power / 1000) * product[2] * kwh_price * quantity
        filament_cost = (product[3] / 1000) * filament_price_kg * quantity
        
        cursor.execute("""
            INSERT INTO sales VALUES (NULL, ?, ?, ?, ?, ?, ?)
        """, (product_id, quantity, product[4] * quantity, filament_cost, energy_cost, datetime.now().date()))
        
        conn.commit()
        conn.close()
    
    def get_products(self):
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("SELECT * FROM products", conn)
        conn.close()
        return df
    
    def get_sales(self):
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("""
            SELECT s.*, p.name as product_name 
            FROM sales s 
            JOIN products p ON s.product_id = p.id
            ORDER BY s.date DESC
        """, conn)
        conn.close()
        return df
    
    def get_financial_summary(self):
        df = self.get_sales()
        if df.empty:
            return {"receita_total": 0, "custo_total": 0, "lucro": 0, "margem": 0}
        
        receita_total = df['sale_price'].sum()
        custo_total = df['filament_cost'].sum() + df['energy_cost'].sum()
        lucro = receita_total - custo_total
        margem = (lucro / receita_total * 100) if receita_total > 0 else 0
        
        return {
            "receita_total": receita_total,
            "custo_total": custo_total,
            "lucro": lucro,
            "margem": margem
        }
    
    def update_settings(self, kwh_price=None, printer_power=None, filament_price=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if kwh_price:
            cursor.execute("UPDATE settings SET value = ? WHERE key = 'kwh_price'", (kwh_price,))
        if printer_power:
            cursor.execute("UPDATE settings SET value = ? WHERE key = 'printer_power'", (printer_power,))
        if filament_price:
            cursor.execute("UPDATE settings SET value = ? WHERE key = 'filament_price_kg'", (filament_price,))
        
        conn.commit()
        conn.close()

def run_dashboard():
    st.set_page_config(page_title="Financeiro 3D", layout="wide")
    
    # Inicializar sistema
    if 'finance_system' not in st.session_state:
        st.session_state.finance_system = FinanceSystem()
    
    fs = st.session_state.finance_system
    
    st.title("💰 Sistema Financeiro - Impressão 3D")
    
    # Sidebar para configurações
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        kwh_price = st.number_input("Preço kWh (R$)", value=0.80, step=0.01)
        printer_power = st.number_input("Potência Impressora (W)", value=200, step=10)
        filament_price = st.number_input("Preço Filamento (R$/kg)", value=80.0, step=1.0)
        
        if st.button("Atualizar Configurações"):
            fs.update_settings(kwh_price, printer_power, filament_price)
            st.success("Configurações atualizadas!")
    
    # Tabs principais
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "📦 Produtos", "💳 Vendas", "📈 Relatórios"])
    
    with tab1:
        # Dashboard principal
        summary = fs.get_financial_summary()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Receita Total", f"R$ {summary['receita_total']:.2f}")
        
        with col2:
            st.metric("Custo Total", f"R$ {summary['custo_total']:.2f}")
        
        with col3:
            st.metric("Lucro", f"R$ {summary['lucro']:.2f}")
        
        with col4:
            st.metric("Margem", f"{summary['margem']:.1f}%")
        
        # Gráficos
        sales_df = fs.get_sales()
        if not sales_df.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Vendas por Produto")
                product_sales = sales_df.groupby('product_name')['quantity'].sum()
                fig = px.pie(values=product_sales.values, names=product_sales.index)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.subheader("Evolução Financeira")
                sales_df['date'] = pd.to_datetime(sales_df['date'])
                daily_sales = sales_df.groupby('date')['sale_price'].sum().cumsum()
                fig = px.line(x=daily_sales.index, y=daily_sales.values)
                fig.update_layout(xaxis_title="Data", yaxis_title="Receita Acumulada (R$)")
                st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.header("📦 Gerenciar Produtos")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("Adicionar Produto")
            name = st.text_input("Nome do Produto")
            print_time = st.number_input("Tempo Impressão (horas)", min_value=0.1, step=0.1)
            filament_weight = st.number_input("Peso Filamento (gramas)", min_value=1.0, step=1.0)
            sale_price = st.number_input("Preço Venda (R$)", min_value=0.01, step=0.01)
            
            if st.button("Adicionar Produto"):
                if name:
                    fs.add_product(name, print_time, filament_weight, sale_price)
                    st.success("Produto adicionado!")
                    st.rerun()
        
        with col2:
            st.subheader("Produtos Cadastrados")
            products = fs.get_products()
            if not products.empty:
                st.dataframe(products, use_container_width=True)
            else:
                st.info("Nenhum produto cadastrado ainda.")
    
    with tab3:
        st.header("💳 Registrar Vendas")
        
        products = fs.get_products()
        
        if not products.empty:
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.subheader("Nova Venda")
                product_options = {f"{row['name']} (R$ {row['sale_price']:.2f})": row['id'] 
                                 for _, row in products.iterrows()}
                
                selected_product = st.selectbox("Selecionar Produto", list(product_options.keys()))
                quantity = st.number_input("Quantidade", min_value=1, value=1)
                
                if st.button("Registrar Venda"):
                    product_id = product_options[selected_product]
                    fs.add_sale(product_id, quantity)
                    st.success("Venda registrada!")
                    st.rerun()
            
            with col2:
                st.subheader("Vendas Recentes")
                sales = fs.get_sales()
                if not sales.empty:
                    # Mostrar apenas colunas relevantes
                    display_cols = ['date', 'product_name', 'quantity', 'sale_price']
                    st.dataframe(sales[display_cols].head(10), use_container_width=True)
                else:
                    st.info("Nenhuma venda registrada ainda.")
        else:
            st.warning("Cadastre produtos antes de registrar vendas.")
    
    with tab4:
        st.header("📈 Relatórios Detalhados")
        
        sales = fs.get_sales()
        
        if not sales.empty:
            # Relatório por período
            st.subheader("Análise de Custos")
            
            total_filament = sales['filament_cost'].sum()
            total_energy = sales['energy_cost'].sum()
            
            cost_data = pd.DataFrame({
                'Tipo de Custo': ['Filamento', 'Energia'],
                'Valor': [total_filament, total_energy]
            })
            
            fig = px.bar(cost_data, x='Tipo de Custo', y='Valor', 
                        title="Distribuição de Custos")
            st.plotly_chart(fig, use_container_width=True)
            
            # Tabela resumo por produto
            st.subheader("Resumo por Produto")
            product_summary = sales.groupby('product_name').agg({
                'quantity': 'sum',
                'sale_price': 'sum',
                'filament_cost': 'sum',
                'energy_cost': 'sum'
            }).round(2)
            
            product_summary['lucro'] = (product_summary['sale_price'] - 
                                       product_summary['filament_cost'] - 
                                       product_summary['energy_cost']).round(2)
            
            st.dataframe(product_summary, use_container_width=True)
        else:
            st.info("Nenhum dado para relatórios ainda.")

if __name__ == "__main__":
    run_dashboard()