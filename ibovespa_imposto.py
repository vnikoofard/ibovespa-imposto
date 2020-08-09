import pandas as pd
import numpy as np
import streamlit as st
import re
import io
import datetime


@st.cache(allow_output_mutation=True)
def cleaning(dataset):

    df_orig.drop([x for x in dataset.columns if x.startswith("Unn")], axis=1 , inplace=True)

    dataset['Data Negócio'] = pd.to_datetime(dataset['Data Negócio'],dayfirst=True)

    def correction(x):
        if "C" in x:
            x = "C"
        elif 'V' in x:
            x = "V"
        return x


    dataset['C/V']=dataset["C/V"].apply(correction)

    def fracionario_to_normal(x):
        if x.endswith("F"):
            x = x[:-1]
        return x

    dataset['Código'] = dataset["Código"].apply(fracionario_to_normal)
    dataset.drop(['Mercado', 'Prazo','Especificação do Ativo' ], axis=1, inplace=True)

    return dataset

def check_consistency(df):

    fail = {'ticker': [], 'date':[], "index":[] }
    for ticker in df["Código"].unique():
        

        if len(df[(df["C/V"] == "V") & (df["Código"] == ticker)].values) > 0:
	#check to insure the sell date is after the purchase date. It guarantee that we have a mean price to calculate the profit.
            
            first_sell_index = df[(df["C/V"] == "V") & (df["Código"] == ticker)]['Data Negócio'].index[0]
            first_sell_date = df.iloc[first_sell_index]['Data Negócio']

         
	#check if the sold ticker has a purchased price. It is important to calculate the mean price of the ticker and then profit.
            if len(df[(df["C/V"] == "C") & (df["Código"] == ticker)]['Data Negócio'].iloc[:first_sell_index]) == 0:
                fail['ticker'].append(ticker)
                fail['index'].append(first_sell_index)
                fail['date'].append(first_sell_date)
                st.write(f"No arquivo tem informação sobre a venda da ação {ticker} na data {first_sell_date} mas está faltando informação sobre a sua compra")
                st.write(f"Por favor insere a informação sobre a compra")
                data_compra = st.date_input(f"A data da compra da ação {ticker}", value = first_sell_date- datetime.timedelta(days=1), max_value=first_sell_date)
                data_compra = pd.to_datetime(data_compra)
                quantidade_compra = st.number_input("Quantidade", min_value=df.iloc[first_sell_index]['Quantidade'])
                preço_compra = st.number_input(label="Preço", min_value = 0.01)
                b = st.button(label="Enter")
                #raise st.ScriptRunner.StopException

                
                if b:
                    line = pd.DataFrame({'Data Negócio':data_compra, 'C/V':"C", 'Código':ticker, 'Quantidade':quantidade_compra
                    , 'Preço (R$)': preço_compra, 'Valor Total (R$)': preço_compra*quantidade_compra}, index = [first_sell_index])
                    df = pd.concat([df.iloc[:first_sell_index], line, df.iloc[first_sell_index:]]).reset_index(drop=True)

                
    

    return df



@st.cache
def general_view(df1):

    df=df1.copy()

    #finding the day-trade operations
    day_trade = {"date":[], "ticker":[], 'index':[]}

    dates = df["Data Negócio"].unique()

    for date in dates:
        tickers = df[df["Data Negócio"]==date]['Código'].unique()
        for ticker in tickers:
            if all(x in df[(df["Data Negócio"]==date) & (df["Código"]==ticker)]["C/V"].values for x in ["C","V"]):
                day_trade['index'].append(df[(df["Data Negócio"]==date) & (df["Código"]==ticker)]["C/V"].index)
                day_trade['date'].append(date)
                day_trade['ticker'].append(ticker)

    day_trade["index"] = [item for sublist in day_trade['index'] for item in sublist]

    #creating a new column to mark the swing/day trades

    df['Day/Swing'] = "Swing"

    df.at[day_trade['index'], 'Day/Swing'] = 'Day'

    #Calculating the operational costs of the negotiations.

    df["Valor Total (R$)"] = np.where(df["C/V"] == "C", -1* df["Valor Total (R$)"], df["Valor Total (R$)"])


    df['Custo de Operação'] = np.where(df["C/V"] == "V", -1*df['Valor Total (R$)'] * (0.000325 + 0.00005),df['Valor Total (R$)'] * (0.000325))

    df['Custo de Operação'] = round(df['Custo de Operação'],3)

    
    #calculationg the mean cost of a purchased stock and its evolution by new acquisition for swing trade. 
    tickers = df["Código"].unique() 
    df["Custo Médio"] = 0.

    for ticker in tickers:
        means = {"Custo":[], "N":[]}
        for index, row in df[(df["Código"] == ticker) & (df['C/V']=='C')].iterrows():
            if index not in day_trade["index"]:
                means["Custo"].append(row["Valor Total (R$)"] +  row['Custo de Operação'])
                means["N"].append(row["Quantidade"])
                mean = -1*sum(means["Custo"])/(sum(means['N']))
                df.at[index,'Custo Médio'] = round(mean,3)
    
    #calculating custo medio for day-trade operations
    for date in day_trade["date"]:
        for ticker in df[df['Data Negócio']==date]["Código"].unique():
            if ticker in day_trade['ticker']:
                day_indices = df[(df['Data Negócio']==date) & (df['Código']==ticker) & (df["C/V"]=='C')].index
                total_quantity = df.iloc[day_indices]["Quantidade"].sum()
                price_sum = df.iloc[day_indices]["Valor Total (R$)"].sum()
                cost_sum = df.iloc[day_indices]['Custo de Operação'].sum()
                total = price_sum + cost_sum
                df.at[day_indices, 'Custo Médio'] = -1*round(total/total_quantity, 3)



    #calculating the profit of each sell

    df["Lucro da Venda"] = 0. 

    indices = df[df["C/V"] == 'V'].index

    for index in indices:
        if df.iloc[index]['Day/Swing'] == "Swing":
            quantity = df.iloc[index]["Quantidade"]
            total = df.iloc[index]["Valor Total (R$)"] + df.iloc[index]["Custo de Operação"]
            ticker = df.iloc[index]["Código"]
            custo_medio = df[(df["Código"] ==ticker) & (df["C/V"] == 'C')].iloc[:index]["Custo Médio"].values[-1]
            df.at[index, "Lucro da Venda"] = round(total - (quantity * custo_medio),3)

        if df.iloc[index]['Day/Swing'] == "Day":
            total = df.iloc[index]["Valor Total (R$)"] + df.iloc[index]["Custo de Operação"]
            ticker = df.iloc[index]["Código"]
            quantity = df.iloc[index]["Quantidade"]
            date = df.iloc[index]["Data Negócio"]
            custo_medio = df[(df["Código"] ==ticker) & (df["C/V"] == 'C')&(df["Data Negócio"]==date)]["Custo Médio"].values[0]
            df.at[index, "Lucro da Venda"] = round(total - (quantity * custo_medio),3)




    

    return df

def day_trade_imposto(df):

    df = df[df["Day/Swing"]=="Day"].copy()
    for index in df.index:
            df.at[index, "DARF"] = df.loc[index]["Lucro da Venda"]* 0.20
    
    df_group = df[['Data Negócio', 'C/V', 'Código', 'Quantidade', 
    'Valor Total (R$)', 'Custo de Operação', 'Lucro da Venda',"Day/Swing", "DARF"]].groupby(['Data Negócio', "Código", "C/V"]).sum()

    imposto_day = df_group['DARF'].sum()

    st.subheader("Day-Trade")

    st.write(f"O total imposto devido em relação as operações day-trade no periodo escolhido é {round(imposto_day,2)}")

    return df_group[df_group['DARF']!=0]


def swing_trade_imposto(df):

    df = df[df["Day/Swing"]=="Swing"].copy()
        
    for y in df["Data Negócio"].dt.year.unique():
        for m in df[df["Data Negócio"].dt.year ==y]["Data Negócio"].dt.month.unique():
            for ticker in df[(df["Data Negócio"].dt.year ==y) & (df["Data Negócio"].dt.month ==m)]["Código"].unique():
                venda_mes = df[(df["C/V"]=="V") & (df["Data Negócio"].dt.month ==m) & (df["Data Negócio"].dt.year ==y) & (df["Código"]==ticker)]['Valor Total (R$)'].sum()
                count = 0
                if venda_mes >= 20000:
                    count = 1
                    for index in df[(df["C/V"] == 'V') & (df["Data Negócio"].dt.month == m) & (df["Data Negócio"].dt.year == y)& (df["Código"]==ticker)].index:
                        df.at[index, "DARF"] = df.loc[index]["Lucro da Venda"]* 0.15


                    valor = df[(df["C/V"] == 'V') & (df["Data Negócio"].dt.month == m) & (df["Data Negócio"].dt.year == y)& (df["Código"]==ticker)]["DARF"].sum()
                    st.subheader("Swing-Trade")
                    st.write(f"O total imposto devido em relação as operações swing-trade no mes {m} do ano {y} escolhido é {round(valor,2)}R$")
                
                    
    if count == 0:
        st.write("Não há nenhuma tributação devido as operações swing-trade no intervalo escolhido.")
    
    df_group = df[['Data Negócio', 'C/V', 'Código', 'Quantidade', 
'Valor Total (R$)','Custo de Operação', 'Lucro da Venda', 'Day/Swing', "DARF"]].groupby(['Data Negócio', "Código", "C/V"]).sum()
    
   
    return df_group[df_group['DARF']!=0]


def impostos(dataset,year ='todos',month='todos',day='todos',modalidade='todos'):

    if modalidade == "todos":
        df = dataset.copy()
    elif modalidade =='day':
        df = dataset[dataset['Day/Swing']=="Day"].copy()
    elif modalidade == 'swing':
        df = dataset[dataset['Day/Swing']=="Swing"].copy()
    else:
        print("Erro de modalidade")

    
    if year != 'todos' and month != 'todos' and day != 'todos':
        df_new = df[(df["Data Negócio"].dt.year == year) & (df["Data Negócio"].dt.month == month) & (df["Data Negócio"].dt.day == day)].copy()
    elif year != 'todos' and month != 'todos':
        df_new = df[(df["Data Negócio"].dt.year == year) & (df["Data Negócio"].dt.month == month)].copy()
    elif year != 'todos':
        df_new = df[(df["Data Negócio"].dt.year == year)].copy()
    else:
        df_new = df.copy()

    #creating a new column for DARF (tax)
    df_new["DARF"] = 0.

    #Calculating the tax for the Day-trades
    if modalidade == 'day':
        df_group = day_trade_imposto(df_new)
        df_group["Day/Swing"] = "Day"

    #Calculating the tax for the Swing-trades
    if modalidade == 'swing':
        df_group = swing_trade_imposto(df_new)
        df_group["Day/Swing"] = "Swing"

    #calculating the tax for both types
    if modalidade =='todos':
        df_group1 = day_trade_imposto(df_new)
        df_group1["Day/Swing"] = "Day"

        df_group2 = swing_trade_imposto(df_new)
        df_group2["Day/Swing"] = "Swing"

        df_group = pd.concat([df_group1,df_group2])

    return df_group




#Initialization
st.title("Análise Tributária do Aviso de Negociação de Ativos (ANA)")
st.markdown("O ANA é um documento emitido por B3 que resume todas as operações no mercado de ações Brasileiro. Esse documento se encontra no [https://cei.b3.com.br](https://cei.b3.com.br), no menu **Extratos e Informativos** -> **Negociação de ativos**. É um arquivo de Excel com nome InfoCEI.xls. É crucial que o arquivo ANA contenha todas as operações pois os preços das compras são necessários para calcular o custo medio de cada ação, ou seja, no arquivo tem que ter no minimo uma compra para cada ação antes da sua venda.")
file_buffer = None
file_buffer = st.file_uploader("Upload o ANA", type=["xls"])
#text_io = io.TextIOWrapper(file_buffer, encoding='utf-8')


if file_buffer is not None:
    df_orig = pd.read_excel(file_buffer, skiprows=10, skipfooter=4)
else:
    df_orig = pd.read_excel("InfoCEI_fake.xls", skiprows=10, skipfooter=4)

df_clean = cleaning(df_orig)

#if  not check_consistency(df_clean):
#    
#    raise st.ScriptRunner.StopException
    #quit()
df_check = check_consistency(df_clean)

#configuration od sidebar
years = df_clean["Data Negócio"].dt.year.unique().tolist()
months = df_clean["Data Negócio"].dt.month.unique().tolist()
days = np.sort(df_clean["Data Negócio"].dt.day.unique()).tolist()

years.insert(0,'todos')
months.insert(0, 'todos')
days.insert(0, 'todos')

st.sidebar.header("Configurar a Data")

year = st.sidebar.selectbox(
    "Escolhe o ano",years)

month = st.sidebar.selectbox(
    "Escolhe o mes", months)

day = st.sidebar.selectbox(
    "Escolhe o dia",days)

modalidade = st.sidebar.selectbox(
    "Escolhe a modalidade (day-trade e/ou swing-trade)",
    ('todos', 'swing', 'day'))

st.header("Uma Visão Geral das Operações")
#main part

df = general_view(df_check)
#st.dataframe(df, width=1024)

st.dataframe(df.style.set_precision(2))

st.header("Os Impostos")

#impostos(df, year= year, month=month, day=day, modalidade=modalidade)
st.dataframe(impostos(df, year= year, month=month, day=day, modalidade=modalidade))

st.markdown('O script desse App se encontra no [ibovespa-imposto](https://github.com/vnikoofard/ibovespa-imposto)')
