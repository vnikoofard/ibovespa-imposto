import pandas as pd
import numpy as np
import streamlit as st
import re
import io
import datetime
import sys

st.set_option('deprecation.showfileUploaderEncoding', False)


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

    dataset.to_csv("df.csv")

    #return dataset


def check_consistency():

    df = pd.read_csv("df.csv", index_col=0)
    df['Data Negócio'] = pd.to_datetime(df['Data Negócio'], dayfirst=True)
    
    #status = True

    fail = {'ticker':'', 'date':'', "index":'' , 'reason':''}
    for ticker in df["Código"].unique():

        if len(df[(df["C/V"] == "V") & (df["Código"] == ticker)].values) > 0:
	#check to insure the sell date is after the purchase date. It guarantee that we have a mean price to calculate the profit.
            
            first_sell_index = df[(df["C/V"] == "V") & (df["Código"] == ticker)]['Data Negócio'].index[0]
            first_sell_date = df.iloc[first_sell_index]['Data Negócio']
            total_sold = df[(df["C/V"] == "V") & (df["Código"]==ticker)]['Quantidade'].sum()
            total_purchased = df[(df["C/V"] == "C") & (df["Código"]==ticker)]['Quantidade'].sum()

         
	#check if the sold ticker has a purchased price. It is important to calculate the mean price of the ticker and then profit.
            if len(df.iloc[:first_sell_index][(df["C/V"] == "C") & (df["Código"] == ticker)]['Data Negócio']) == 0:
                fail['ticker'] = ticker
                fail['index'] = first_sell_index
                fail['date'] = first_sell_date
                fail['reason'] = 'before'
                status = True
                break
    #check if there are more sold stocks than the purchased ones.
            elif total_sold>total_purchased:
                fail['ticker'] = ticker
                fail['index'] = first_sell_index
                fail['date'] = first_sell_date
                fail['reason'] = 'less'
                status = True
                break
                
            else:
                status = False        
                
    return status ,fail

def add(fail):
    df = pd.read_csv("df.csv", index_col=0)
    df['Data Negócio'] = pd.to_datetime(df['Data Negócio'], dayfirst=True)

    
    ticker, first_sell_date, first_sell_index, reason = fail.values()

    if reason == 'before': 
        st.subheader('AVISO')
        st.markdown(f'''No arquivo tem informação sobre a venda da ação **{ticker}** na data **{first_sell_date.date()}** 
        mas está faltando informação sobre a sua compra nos dias anteriores''')

        data_compra = st.date_input(f"A data da compra da ação {ticker}", value = first_sell_date- datetime.timedelta(days=1), max_value=first_sell_date)
        data_compra = pd.to_datetime(data_compra)
        quantidade_compra = st.number_input("Quantidade", min_value=df.iloc[first_sell_index]['Quantidade'])
        preço_compra = st.number_input(label="Preço", min_value = 0.)

        if st.button(label="Click 2X", key=1):
            line = pd.DataFrame({'Data Negócio':data_compra, 'C/V':"C", 'Código':ticker, 'Quantidade':quantidade_compra
            , 'Preço (R$)': preço_compra, 'Valor Total (R$)': preço_compra*quantidade_compra}, index = [first_sell_index])
            df = pd.concat([df.iloc[:first_sell_index], line, df.iloc[first_sell_index:]]).reset_index(drop=True)
            df.sort_index(inplace=True)
            df.to_csv("df.csv")

    if reason == 'less':
        total_sold = df[(df["C/V"] == "V") & (df["Código"]==ticker)]['Quantidade'].sum()
        total_purchased = df[(df["C/V"] == "C") & (df["Código"]==ticker)]['Quantidade'].sum()
        different = total_sold - total_purchased
        st.subheader('AVISO')
        st.markdown(f"No arquivo tem mais {different} venda da ação {ticker} do que compra. Por favor informa a data e o preço da compra.")
        
        data_compra = st.date_input(f"A data da compra da ação {ticker}", value = first_sell_date- datetime.timedelta(days=1))
        data_compra = pd.to_datetime(data_compra)
        quantidade_compra = st.number_input("Quantidade", min_value=different)
        preço_compra = st.number_input(label="Preço", min_value = 0.)

        if st.button(label="Enter 2X ", key=2):
            line = pd.DataFrame({'Data Negócio':data_compra, 'C/V':"C", 'Código':ticker, 'Quantidade':quantidade_compra
            , 'Preço (R$)': preço_compra, 'Valor Total (R$)': preço_compra*quantidade_compra}, index = [first_sell_index])
            df = pd.concat([df.iloc[:first_sell_index], line, df.iloc[first_sell_index:]]).reset_index(drop=True)
            df.sort_index(inplace=True)
            df.to_csv("df.csv")

    
    
    #raise st.ScriptRunner.StopException


@st.cache
def general_view():
    df = pd.read_csv("df.csv", index_col=0)
    df['Data Negócio'] = pd.to_datetime(df['Data Negócio'],dayfirst=True)
    df.sort_index(inplace=True)

    #df=df1.copy()

    #finding the DT-trade operations
    DT_trade = {"date":[], "ticker":[], 'index':[]}

    dates = df["Data Negócio"].unique()

    for date in dates:
        tickers = df[df["Data Negócio"]==date]['Código'].unique()
        for ticker in tickers:
            if all(x in df[(df["Data Negócio"]==date) & (df["Código"]==ticker)]["C/V"].values for x in ["C","V"]):
                DT_trade['index'].append(df[(df["Data Negócio"]==date) & (df["Código"]==ticker)]["C/V"].index)
                DT_trade['date'].append(date)
                DT_trade['ticker'].append(ticker)

    DT_trade["index"] = [item for sublist in DT_trade['index'] for item in sublist]

    #creating a new column to mark the ST/DT trades

    df['DT/ST'] = "ST"

    df.at[DT_trade['index'], 'DT/ST'] = 'DT'

    #Calculating the operational costs of the operations.
    #the Valor for the purchased stocks turns to negative cuz we loss money!
    df["Valor Total (R$)"] = np.where(df["C/V"] == "C", -1* df["Valor Total (R$)"], df["Valor Total (R$)"])

    # the below costs are strange! I havnt found them in the website of Clear
    #df['Custo de Operação-ST'] = np.where(df["C/V"] == "V", -1*df['Valor Total (R$)'] * (0.000325 + 0.00005),df['Valor Total (R$)'] * (0.000325))

    df['Custos-ST'] = -1*abs(df['Valor Total (R$)'] * (0.000275 + 0.00005))
    df['Custos-ST'] = round(df['Custos-ST'],3)

    df['Custos-DT'] = 0.

    #calculating in a DT-trade how stocks are divided between ST-trade e DT-trade
    df['Quant-DT'] = 0
    df['Quant-ST'] = df["Quantidade"]
    df['Lucro-DT'] = 0. 
    df['Lucro-ST'] = 0. 

    for DT in DT_trade['date']:
        for ticker in df[(df["Data Negócio"]==DT)&(df['DT/ST'] == "DT")]["Código"].unique() :
            dt = df[(df["Data Negócio"]==DT) & (df["Código"]==ticker)]
            sell_list = []
            purchase_list = []
            for index,row in dt.iterrows():
                if row['C/V'] == 'V':
                    sell_list.append(index)
                if row['C/V'] == 'C':
                    purchase_list.append(index)
    
            for s_index, p_index in zip(sell_list,purchase_list):
                sell_quantity = df.iloc[s_index]["Quantidade"]
                purchase_quantity = df.iloc[p_index]["Quantidade"]
                sell_price = df.iloc[s_index]["Preço (R$)"]
                purchase_price = df.iloc[p_index]["Preço (R$)"]
                dt_quantity = min(sell_quantity, purchase_quantity)
                st_quantity = max(sell_quantity, purchase_quantity) - dt_quantity
                dt_operation_cost = dt_quantity*(sell_price + purchase_price) * (0.0002 + 0.00005)
                
                df.at[p_index, 'Custos-DT'] = -1*abs(dt_quantity*(purchase_price) * (0.0002 + 0.00005))
                df.at[s_index, 'Custos-DT'] = -1*abs(dt_quantity*(sell_price) * (0.0002 + 0.00005))

                df.at[s_index,'Quant-DT'] = dt_quantity
                df.at[s_index,'Quant-ST'] = df.iloc[s_index]["Quantidade"] - dt_quantity

                #As some part of negociation might be ST trade
                df.at[p_index, 'Custos-ST'] = -1*abs(st_quantity*(purchase_price) * (0.000275 + 0.00005))
                df.at[s_index, 'Custos-ST'] = -1*abs(st_quantity*(sell_price) * (0.000275 + 0.00005))

                df.at[p_index, 'Quant-DT'] = dt_quantity
                df.at[p_index, 'Quant-ST'] = df.iloc[p_index]["Quantidade"] - dt_quantity
                df.at[s_index, 'Lucro-DT'] = dt_quantity * (sell_price - purchase_price) - dt_operation_cost

            #correcting "DT" to "ST"
            s = [x[0] for x in zip(sell_list,purchase_list)] 
            s2 = [x for x in sell_list if x not in s]
            df.at[s2, 'DT/ST'] = "ST"

            p = [x[1] for x in zip(sell_list,purchase_list)] 
            p2 = [x for x in purchase_list if x not in p]
            df.at[p2, 'DT/ST'] = "ST"
            

    #calculationg the mean cost of a purchased stock and its evolution by new acquisition for ST trade. 
    tickers = df["Código"].unique() 
    # for calculating the mean cost we need to follow the positions of each ticker in each operation.
    # If position==0 the mean cost resets to the first purchase's price.
    df["Posição"] = 0
    for ticker in tickers:
        position = 0
        for index, row in df[(df["Código"] == ticker)].iterrows():
            if row['Quant-DT'] == 0 or row['Quant-ST'] != 0:
                try: 
                    if row['C/V'] == 'C':
                        position = position + row['Quant-ST']
                        df.at[index,"Posição"] = position 
                        

                    elif row['C/V'] == 'V':
                        position = position - row['Quant-ST']
                        df.at[index,"Posição"] = position
                        

                except:
                    st.write(f"Erro no calculo de posição da ação {ticker} na data {row['Data Negócio']}")
            
            
    #using the df['Position'] is possible to calculate the mean cost.
    df["PM"] = 0.
    for ticker in tickers:
        position_prev = 0
        mean_prev = 0
    #calculating custo medio for ST-trade operations 
        for index, row in df[(df["Código"] == ticker)].iterrows():
            if row['Quant-ST'] != 0:
                
                try:
                    if row['C/V']=='C':
                        if position_prev == 0:
                            medio = (row['Quant-ST']*row['Preço (R$)'] -row['Custos-ST'])/row['Quant-ST']
                            df.at[index,"PM"] = medio
                            mean_prev = medio
                            position_prev = row['Posição']
                        else:
                            
                            medio = (mean_prev*position_prev + row['Quant-ST']*row['Preço (R$)'] -row['Custos-ST'])/\
                                (row['Quant-ST'] + position_prev)
                            df.at[index,"PM"] = medio
                            mean_prev = medio
                            position_prev = row['Posição']

                    if row['C/V']=='V':
                        #mean_prev = row["PM"]
                        position_prev = row['Posição']
                        


                except:
                    st.write(f"Erro no calculo do custo medio no {ticker} na data {row['Data Negócio']}, error{sys.exc_info()}")
                    st.write(row['Quant-ST'], position_prev)

                
    #calculating the profit of each sell

    #for ST-trade
    for ticker in tickers:
        for index, row in df[(df["Código"] == ticker)].iterrows():
            if row['Quant-ST'] != 0:
                if row["C/V"] == 'C':
                    mean_cost = row['PM']
                elif row["C/V"] == 'V':
                    gain = row['Quant-ST']*row['Preço (R$)'] + row["Custos-ST"]
                    costs = row['Quant-ST']*mean_cost #mean_cost is a negative value cuz we have paid money to purchase a stock
                    net_gain = round(gain - costs,3)
                    df.at[index, 'Lucro-ST'] = net_gain
        

    return df


def DT_trade_imposto(df):

    df = df[df["DT/ST"]=="DT"].copy()
    for index in df.index:
            df.at[index, "DARF"] = df.loc[index]["Lucro-DT"]* 0.20
    
    df_group = df[['Data Negócio', 'C/V', 'Código', 'Quantidade', 
    'Valor Total (R$)', 'Lucro-ST', 'Lucro-DT',"DT/ST", "DARF"]].groupby(['Data Negócio', "Código", "C/V"]).sum()

    imposto_DT = df_group['DARF'].sum()

    st.subheader("DT-Trade")

    st.write(f"O total imposto devido em relação as operações DT-trade no periodo escolhido é {round(imposto_DT,2)}")

    return df_group[df_group['DARF']!=0]


def ST_trade_imposto(df):

    df = df[df["DT/ST"]=="ST"].copy()
        
    for y in df["Data Negócio"].dt.year.unique():
        for m in df[df["Data Negócio"].dt.year ==y]["Data Negócio"].dt.month.unique():
            venda_mes = df[(df["C/V"]=="V") & (df["Data Negócio"].dt.month ==m) & (df["Data Negócio"].dt.year ==y)]['Valor Total (R$)'].sum()
            count = 0
            if venda_mes >= 20000:
                count = 1
                for index in df[(df["C/V"] == 'V') & (df["Data Negócio"].dt.month == m) & (df["Data Negócio"].dt.year == y)].index:
                    df.at[index, "DARF"] = df.loc[index]["Lucro-ST"]* 0.15


                valor = df[(df["C/V"] == 'V') & (df["Data Negócio"].dt.month == m) & (df["Data Negócio"].dt.year == y)]["DARF"].sum()
                st.subheader("ST-Trade")
                st.write(f"O total imposto devido em relação as operações ST-trade no mes {m} do ano {y} escolhido é {round(valor,2)}R$")
                
                    
    if count == 0:
        st.write("Não há nenhuma tributação devido as operações ST-trade no intervalo escolhido.")
    
    df_group = df[['Data Negócio', 'C/V', 'Código', 'Quantidade', 
'Valor Total (R$)','Lucro-ST', 'Lucro-DT', 'DT/ST', "DARF"]].groupby(['Data Negócio', "Código", "C/V"]).sum()
    
   
    return df_group[df_group['DARF']!=0]


def impostos(dataset,year ='todos',month='todos',DT='todos',modalidade='todos'):

    if modalidade == "todos":
        df = dataset.copy()
    elif modalidade =='DT':
        df = dataset[dataset['DT/ST']=="DT"].copy()
    elif modalidade == 'ST':
        df = dataset[dataset['DT/ST']=="ST"].copy()
    else:
        print("Erro de modalidade")

    
    if year != 'todos' and month != 'todos' and DT != 'todos':
        df_new = df[(df["Data Negócio"].dt.year == year) & (df["Data Negócio"].dt.month == month) & (df["Data Negócio"].dt.DT == DT)].copy()
    elif year != 'todos' and month != 'todos':
        df_new = df[(df["Data Negócio"].dt.year == year) & (df["Data Negócio"].dt.month == month)].copy()
    elif year != 'todos':
        df_new = df[(df["Data Negócio"].dt.year == year)].copy()
    else:
        df_new = df.copy()

    #creating a new column for DARF (tax)
    df_new["DARF"] = 0.

    #Calculating the tax for the DT-trades
    if modalidade == 'DT':
        df_group = DT_trade_imposto(df_new)
        df_group["DT/ST"] = "DT"

    #Calculating the tax for the ST-trades
    if modalidade == 'ST':
        df_group = ST_trade_imposto(df_new)
        df_group["DT/ST"] = "ST"

    #calculating the tax for both types
    if modalidade =='todos':
        df_group1 = DT_trade_imposto(df_new)
        df_group1["DT/ST"] = "DT"

        df_group2 = ST_trade_imposto(df_new)
        df_group2["DT/ST"] = "ST"

        df_group = pd.concat([df_group1,df_group2])

    return df_group




#Initialization
st.title("Análise Tributária do Aviso de Negociação de Ativos (ANA)")
st.markdown("O ANA é um documento emitido por B3 que resume todas as operações no mercado de ações Brasileiro. Esse documento se encontra no [https://cei.b3.com.br](https://cei.b3.com.br), no menu **Extratos e Informativos** -> **Negociação de ativos**. É um arquivo de Excel com nome InfoCEI.xls. É crucial que o arquivo ANA contenha todas as operações pois os preços das compras são necessários para calcular o custo medio de cada ação, ou seja, no arquivo tem que ter no minimo uma compra para cada ação antes da sua venda.")

#file_buffer = None
file_buffer = st.file_uploader("Upload o ANA", type=["xls"])
#text_io = io.TextIOWrapper(file_buffer, encoding='utf-8')

if file_buffer:
    df_orig = pd.read_excel(file_buffer, skiprows=10, skipfooter=4)

    cleaning(df_orig)

    status, fail = check_consistency()
    #st.write(status, fail)
    if status:
        #st.write("Add function trigged")
        add(fail)
    else: 
        #st.write("General View launched")
        df = general_view()
        #configuration od sidebar
        years = df["Data Negócio"].dt.year.unique().tolist()
        months = df["Data Negócio"].dt.month.unique().tolist()
        days = np.sort(df["Data Negócio"].dt.day.unique()).tolist()

        month_convert= {1: "Janeiro", 2:"Fevereiro", 3:"Março", 4:'April', 5: 'Maio', 6:"Junho", 7:'Julho', 8:"Agosto",
        9: "Setembro", 10: "Outubro", 11:"Novembro", 12:'Dezembro'}

        months = [month_convert[i] for i in months]

        years.insert(0,'todos')
        months.insert(0, 'todos')
        days.insert(0, 'todos')

        st.sidebar.header("Configurar a Data")

        year = st.sidebar.selectbox(
            "Escolhe o ano",years)

        month = st.sidebar.selectbox(
            "Escolhe o mes", months)
        if month != 'todos':
            month = [i for i in month_convert.keys() if month_convert[i]==month][0]

        DT = st.sidebar.selectbox(
            "Escolhe o dia",days)

        modalidade = st.sidebar.selectbox(
            "Escolhe a modalidade (DT-trade e/ou ST-trade)",
            ('todos', 'ST', 'DT'))

        st.header("Uma Visão Geral das Operações")

        #main part

        #df = general_view(df_check)
        #st.dataframe(df, width=1024)
        df_show = df.copy()
        df_show['Data Negócio'] = df_show['Data Negócio'].dt.date
        st.dataframe(df_show.style.set_precision(2))

        st.header("Os Impostos")

        #impostos(df, year= year, month=month, DT=DT, modalidade=modalidade)
        st.dataframe(impostos(df, year= year, month=month, DT=DT, modalidade=modalidade))

        st.markdown('O script desse App se encontra no Github [ibovespa-imposto](https://github.com/vnikoofard/ibovespa-imposto)')
