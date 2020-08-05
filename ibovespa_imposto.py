import pandas as pd
import numpy as np
import streamlit as st
import re
import io


@st.cache(allow_output_mutation=True)
def cleaning(dataset):
    col_drop = []
    for col in dataset.columns:
        if re.match(r"Unna", col):
            col_drop.append(col)
    if col_drop:
        dataset.drop(col_drop, axis=1, inplace=True)

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

    
    #calculationg the mean cost of a purchased stock and its evolution by new acquisition. 
    tickers = df["Código"].unique() 
    df["Custo Médio"] = 0.

    for ticker in tickers:
        means = {"Custo":[], "N":[]}
        for index, row in df[(df["Código"] == ticker) & (df['C/V']=='C')].iterrows():
            means["Custo"].append(row["Valor Total (R$)"] +  row['Custo de Operação'])
            means["N"].append(row["Quantidade"])
            mean = -1*sum(means["Custo"])/(sum(means['N']))
            df.at[index,'Custo Médio'] = round(mean,3)

    #calculating the profit of each sell

    df["Lucro da Venda"] = 0.

    indices = df[df["C/V"] == 'V'].index

    for index in indices:
        quantity = df.loc[index]["Quantidade"]
        total = df.loc[index]["Valor Total (R$)"] + df.loc[index]["Custo de Operação"]
        ticker = df.loc[index]["Código"]
        custo_medio = df[(df["Código"] ==ticker) & (df["C/V"] == 'C')].loc[:index]["Custo Médio"].values[-1]
        df.at[index, "Lucro da Venda"] = total - (quantity * custo_medio)

    

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
                
                if venda_mes >= 20000:
                    for index in df[(df["C/V"] == 'V') & (df["Data Negócio"].dt.month == m) & (df["Data Negócio"].dt.year == y)& (df["Código"]==ticker)].index:
                        df.at[index, "DARF"] = df.loc[index]["Lucro da Venda"]* 0.15


                    valor = df[(df["C/V"] == 'V') & (df["Data Negócio"].dt.month == m) & (df["Data Negócio"].dt.year == y)& (df["Código"]==ticker)]["DARF"].sum()
                    st.subheader("Swing-Trade")
                    st.write(f"O total imposto devido em relação as operações swing-trade no mes {m} do ano {y} escolhido é {round(valor,2)}R$")

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
st.title("Analise do Aviso de Negociação de Ativos (ANA)")
st.write("O ANA se encontra no www.cei.b3.com.br, no menu Extratos e Informativos -> Negociação de ativos. É um arquivo de Excel com nome InfoCEI.xls.")
file_buffer = None
file_buffer = st.file_uploader("Upload o ANA", type=["xls"])
#text_io = io.TextIOWrapper(file_buffer, encoding='utf-8')


if file_buffer is not None:
    df_orig = pd.read_excel(file_buffer, skiprows=10, skipfooter=4)
else:
    df_orig = pd.read_excel("InfoCEI_fake.xls", skiprows=10, skipfooter=4)

df_clean = cleaning(df_orig)

#configuration od sidebar
years = df_clean["Data Negócio"].dt.year.unique().tolist()
months = df_clean["Data Negócio"].dt.month.unique().tolist()
days = df_clean["Data Negócio"].dt.day.unique().tolist()

years.insert(0,'todos')
months.insert(0, 'todos')
days.insert(0, 'todos')


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

df = general_view(df_clean)
#st.dataframe(df, width=1024)

st.dataframe(df.style.set_precision(2))

st.header("Os Impostos")

#impostos(df, year= year, month=month, day=day, modalidade=modalidade)
st.dataframe(impostos(df, year= year, month=month, day=day, modalidade=modalidade))