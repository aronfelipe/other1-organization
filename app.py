import os
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st
import plotly.express as px

DB_DIR = "/data"                      # volume do Railway
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "app.db")

class FinanceSystem:
    def _init_(self, db_path=DB_PATH):
        self.db_path = db_path
        self.setup_database()

    def setup_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                print_time REAL NOT NULL,       -- horas
                filament_weight REAL NOT NULL,  -- gramas
                sale_price REAL NOT NULL        -- R$
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                sale_price REAL NOT NULL,
                filament_cost REAL NOT NULL,
                energy_cost REAL NOT NULL,
                date TEXT NOT NULL,
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value REAL
            )
        """)

        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('kwh_price', 0.80)")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('printer_power', 200)")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('filament_price_kg', 80.0)")

        conn.commit()
        conn.close()

    def add_product(self, name, print_time, filament_weight, sale_price):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO products (name, print_time, filament_weight, sale_price) VALUES (?, ?, ?, ?)",
            (name, float(print_time), float(filament_weight), float(sale_price))
        )
        conn.commit()
        conn.close()

    def add_sale(self, product_id, quantity=1):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT id, name, print_time, filament_weight, sale_price FROM products WHERE id = ?", (product_id,))
        product = cursor.fetchone()
        if not product:
            conn.close()
            raise ValueError("Produto não encontrado.")

        cursor.execute("SELECT value FROM settings WHERE key = 'kwh_price'")
        kwh_price = float(cursor.fetchone()[0])
        cursor.execute("SELECT value FROM settings WHERE key = 'printer_power'")
        printer_power = float(cursor.fetchone()[0])  # Watts
        cursor.execute("SELECT value FROM settings WHERE key = 'filament_price_kg'")
        filament_price_kg = float(cursor.fetchone()[0])

        # Cálculos
        print_time_h = float(product[2])
        filament_g = float(product[3])
        sale_unit = float(product[4])

        energy_cost = (printer_power / 1000.0) * print_time_h * kwh_price * quantity
        filament_cost = (filament_g / 1000.0) * filament_price_kg * quantity

        cursor.execute("""
            INSERT INTO sales (product_id, quantity, sale_price, filament_cost, energy_cost, date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (product_id, int(quantity), sale_unit * quantity, filament_cost, energy_cost, datetime.now().date().isoformat()))

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
            SELECT s.*, p.name AS product_name
            FROM sales s
            JOIN products p ON s.product_id = p.id
            ORDER BY s.date DESC, s.id DESC
        """, conn)
        conn.close()
        return df

    def get_financial_summary(self):
        df = self.get_sales()
        if df.empty:
            return {"receita_total": 0.0, "custo_total": 0.0, "lucro": 0.0, "margem": 0.0}
        receita_total = float(df['sale_price'].sum())
        custo_total = float(df['filament_cost'].sum() + df['energy_cost'].sum())
        lucro = receita_total - custo_total
        margem = (lucro / receita_total * 100.0) if receita_total > 0 else 0.0
        return {"receita_total": receita_total, "custo_total": custo_total, "lucro": lucro, "margem": margem}

    def update_settings(self, kwh_price=None, printer_power=None, filament_price=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        if kwh_price is not None:
            cursor.execute("UPDATE settings SET value = ? WHERE key = 'kwh_price'", (float(kwh_price),))
        if printer_power is not None:
            cursor.execute("UPDATE settings SET value = ? WHERE key = 'printer_power'", (float(printer_power),))
        if filament_price is not None:
            cursor.execute("UPDATE settings SET value = ? WHERE key = 'filament_price_kg'", (float(filament_price),))
        conn.commit()
        conn.close()


def run_dashboard():
    st.set_page_config(page_title="Financeiro 3D", layout="wide")
    if 'finance_system' not in st.session_state:
        st.session_state.finance_system = FinanceSystem()

    fs = st.session_state.finance_system
    st.title("💰 Sistema Financeiro - Impressão 3D")

    with st.sidebar:
        st.header("⚙ Configurações")
        # Lê atuais
        kwh_price = st.number_input("Preço kWh (R$)", value=0.80, step=0.01, format="%.2f")
        printer_power = st.number_input("Potência Impressora (W)", value=200, step=10)
        filament_price = st.number_input("Preço Filamento (R$/kg)", value=80.0, step=1.0, format="%.2f")
        if st.button("Atualizar Configurações"):
            fs.update_settings(kwh_price, printer_power, filament_price)
            st.success("Configurações atualizadas!")

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "📦 Produtos", "💳 Vendas", "📈 Relatórios"])

    with tab1:
        summary = fs.get_financial_summary()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Receita Total", f"R$ {summary['receita_total']:.2f}")
        c2.metric("Custo Total", f"R$ {summary['custo_total']:.2f}")
        c3.metric("Lucro", f"R$ {summary['lucro']:.2f}")
        c4.metric("Margem", f"{summary['margem']:.1f}%")

        sales_df = fs.get_sales()
        if not sales_df.empty:
            left, right = st.columns(2)

            with left:
                st.subheader("Vendas por Produto")
                prod = sales_df.groupby('product_name', as_index=False)['quantity'].sum()
                fig = px.pie(prod, values='quantity', names='product_name', hole=0.3)
                st.plotly_chart(fig, use_container_width=True)

            with right:
                st.subheader("Evolução Financeira")
                sales_df['date'] = pd.to_datetime(sales_df['date'])
                daily = sales_df.groupby('date', as_index=False)['sale_price'].sum()
                daily['receita_acumulada'] = daily['sale_price'].cumsum()
                fig = px.line(daily, x='date', y='receita_acumulada',
                              labels={'date': 'Data', 'receita_acumulada': 'Receita Acumulada (R$)'})
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem vendas ainda. Cadastre produtos e registre a primeira venda.")

    with tab2:
        st.header("📦 Gerenciar Produtos")
        col1, col2 = st.columns([1, 2])
        with col1:
            st.subheader("Adicionar Produto")
            name = st.text_input("Nome do Produto")
            print_time = st.number_input("Tempo de Impressão (horas)", min_value=0.1, step=0.1)
            filament_weight = st.number_input("Peso de Filamento (g)", min_value=1.0, step=1.0)
            sale_price = st.number_input("Preço de Venda (R$)", min_value=0.01, step=0.01)
            if st.button("Adicionar Produto"):
                if name.strip():
                    fs.add_product(name.strip(), print_time, filament_weight, sale_price)
                    st.success("Produto adicionado!")
                    st.rerun()
                else:
                    st.warning("Informe um nome.")

        with col2:
            st.subheader("Produtos Cadastrados")
            products = fs.get_products()
            st.dataframe(products, use_container_width=True) if not products.empty else st.info("Nenhum produto cadastrado.")

    with tab3:
        st.header("💳 Registrar Vendas")
        products = fs.get_products()
        if not products.empty:
            col1, col2 = st.columns([1, 2])
            with col1:
                st.subheader("Nova Venda")
                options = {f"{row['name']} (R$ {row['sale_price']:.2f})": int(row['id']) for _, row in products.iterrows()}
                selected = st.selectbox("Selecionar Produto", list(options.keys()))
                quantity = st.number_input("Quantidade", min_value=1, value=1)
                if st.button("Registrar Venda"):
                    fs.add_sale(options[selected], quantity)
                    st.success("Venda registrada!")
                    st.rerun()
            with col2:
                st.subheader("Vendas Recentes")
                sales = fs.get_sales()
                if not sales.empty:
                    st.dataframe(sales[['date', 'product_name', 'quantity', 'sale_price']].head(20), use_container_width=True)
                else:
                    st.info("Nenhuma venda registrada ainda.")
        else:
            st.warning("Cadastre produtos antes de registrar vendas.")

    with tab4:
        st.header("📈 Relatórios Detalhados")
        sales = fs.get_sales()
        if not sales.empty:
            st.subheader("Análise de Custos")
            total_filament = float(sales['filament_cost'].sum())
            total_energy = float(sales['energy_cost'].sum())
            cost_data = pd.DataFrame({'Tipo de Custo': ['Filamento', 'Energia'],
                                      'Valor': [total_filament, total_energy]})
            fig = px.bar(cost_data, x='Tipo de Custo', y='Valor', title="Distribuição de Custos")
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("Resumo por Produto")
            summary = sales.groupby('product_name').agg(
                quantidade=('quantity', 'sum'),
                receita=('sale_price', 'sum'),
                custo_filamento=('filament_cost', 'sum'),
                custo_energia=('energy_cost', 'sum')
            )
            summary['lucro'] = summary['receita'] - summary['custo_filamento'] - summary['custo_energia']
            st.dataframe(summary.round(2), use_container_width=True)
        else:
            st.info("Nenhum dado para relatórios ainda.")

if _name_ == "_main_":
    run_dashboard()