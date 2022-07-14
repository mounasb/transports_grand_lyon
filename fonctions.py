import pandas as pd
import json
import requests
import datetime as dt
import pytz
import folium
from folium.plugins import MarkerCluster
from fuzzywuzzy import fuzz
import geopandas as gpd
from shapely.geometry import Point
import plotly.express as px


# Paramétrage
color_red_st = '#FF4B4B'

# Authentification
import base64
from requests.auth import HTTPBasicAuth
# USERNAME = st.secrets["USERNAME"]
# PASSWORD = st.secrets["PASSWORD"]


def get_request_json(r):
    """ Retourne un DataFrame"""
    df = pd.json_normalize(r.json(), record_path='values')
    return df


def get_request_geojson(r):
    """ Retourne un DataFrame"""
    df = pd.json_normalize(r.json(), record_path='features')
    return df


def get_df_velov_tr():
    """ Récupère les disponibilités en temps réel des Vélo'v depuis l'API du Grand Lyon
        Retourne un DataFrame """

    link_velov = "https://download.data.grandlyon.com/ws/rdata/jcd_jcdecaux.jcdvelov/all.json?maxfeatures=-1&start=1"
    r_velov = requests.get(link_velov)
    bikes = get_request_json(r_velov)

    # insertion d'un timestamp
    t = [dt.datetime.now(pytz.timezone('Europe/Paris')).replace(microsecond=0) for i in range(len(bikes))]
    s = pd.Series(t, name = 'timestamp')
    bikes.insert(0, 'timestamp', s)

    columns_to_keep = ['timestamp', 'address', 'availability', 'available_bike_stands',
                       'available_bikes', 'bike_stands', 'lat', 'lng', 'name', 'status',]

    bikes = bikes[columns_to_keep]

    # transformer les colonnes de coordonnées en float
    bikes['lat'] = bikes['lat'].astype('float64')
    bikes['lng'] = bikes['lng'].astype('float64')

    return bikes


def get_map_velov_tr(df):
    """  Input = DataFrame velov temps réel
         Génère une carte Folium, l'exporte en html
         Eetourne le nom du fichier (str)"""

    centre = [45.7548790164649, 4.84367508189202]       # Guillotière
    map_velov = folium.Map(location=centre, zoom_start=14)
    map_velov.add_child(folium.TileLayer("cartodbpositron"))
    velov_cluster = MarkerCluster(name="Velo'v cluster").add_to(map_velov)

    # ajout marqueurs
    for i in range(len(df)):
        status = df.loc[i]['status']
        # loc = bikes.loc[i]['point_coord']
        loc = [df.loc[i]['lat'], df.loc[i]['lng']]
        velos_dispo = df.loc[i]['available_bikes']
        places_dispo = df.loc[i]['available_bike_stands']
        availability = df.loc[i]['availability']
        nom = df.loc[i]['name']
        adresse = df.loc[i]['address']
        max_width = 220
        seuil_velo = 3

        if velos_dispo > 1:
            v_dispo = 'vélos disponibles'
        else:
            v_dispo = 'vélo disponible'
        if places_dispo > 1:
            p_dispo = 'places disponibles'
        else:
            p_dispo = 'place disponible'

        if nom:
            pop = folium.Popup(f"<b>{nom}</b><br>• {velos_dispo} {v_dispo}<br>• {places_dispo} {p_dispo}", max_width=max_width)
        else:
            pop = folium.Popup(f"<b>{adresse}</b><br>• {velos_dispo} {v_dispo}<br>• {places_dispo} {p_dispo}", max_width=max_width)

        if status == 'CLOSED':
            icon = folium.Icon(color='gray', icon='glyphicon-remove')
            pop = folium.Popup(f"<b>{df.loc[i]['name']}</b><br>• STATION FERMÉE", max_width=max_width)
        else:
            if not availability:
                pop = folium.Popup(f"<b>{nom}</b><br>Données non disponibles", max_width=max_width)
                icon = folium.Icon(color='gray', icon="question-circle", prefix='fa')
            else:
                velos_dispo = int(df.loc[i]['available_bikes'])
                places_dispo = int(df.loc[i]['available_bike_stands'])
                if velos_dispo == 0:
                    icon = folium.Icon(color='red', icon="glyphicon-ban-circle")
                elif velos_dispo <= seuil_velo:
                    icon = folium.Icon(color="orange", icon="glyphicon-exclamation-sign")
                else:
                    icon = folium.Icon(color='darkblue', icon="bicycle", prefix="fa")

        folium.Marker(
            location=loc,
            popup=pop,
            icon=icon,
            ).add_to(velov_cluster)

    filename = 'data_grand_lyon/map_velov.html'
    map_velov.save(filename)

    return filename


def get_all_traces_color():
    """ Récupère les traces de toutes les lignes TCL depuis 3 API du Grand Lyon,
        construit une carte, exporte un fichier html, et retourne le nom du fichier (str)"""

    # API tracés de tram
    link_tram = "https://download.data.grandlyon.com/wfs/rdata?SERVICE=WFS&VERSION=2.0.0&request=GetFeature&typename=tcl_sytral.tcllignetram_2_0_0&outputFormat=application/json; subtype=geojson&SRSNAME=EPSG:4171"
    r_tram = requests.get(link_tram)
    traces_tram = pd.json_normalize(r_tram.json())
    traces_tram = traces_tram['features'][0]

    # API tracés de bus
    link_bus = 'https://download.data.grandlyon.com/wfs/rdata?SERVICE=WFS&VERSION=2.0.0&request=GetFeature&typename=tcl_sytral.tcllignebus_2_0_0&outputFormat=application/json; subtype=geojson&SRSNAME=EPSG:4171'
    r_bus = requests.get(link_bus)
    traces_bus = pd.json_normalize(r_bus.json())
    t_bus = traces_bus['features'][0]

    # API tracés métro & funiculaires
    link_metro = "https://download.data.grandlyon.com/wfs/rdata?SERVICE=WFS&VERSION=2.0.0&request=GetFeature&typename=tcl_sytral.tcllignemf_2_0_0&outputFormat=application/json; subtype=geojson&SRSNAME=EPSG:4171&startIndex=0"
    r_metro = requests.get(link_metro)
    traces_metro = pd.json_normalize(r_metro.json())
    traces_metro = traces_metro['features'][0]
    t_fun = [t for t in traces_metro if t['properties']['famille_transport']=='FUN']
    t_metro = [t for t in traces_metro if t['properties']['famille_transport']=='MET']

    # construction dictionnaire avec les tracés bus, métro, funiculaires, tram
    lines_dict = {}
    lines_dict['Bus'] = t_bus
    lines_dict['Tramway'] = traces_tram
    lines_dict['Métro'] = t_metro
    lines_dict['Funiculaire'] = t_fun

    # CARTE
    # paramétrage :
    centre = [45.75540611072912, 4.842535168843551]      # Guillotière
    map = folium.Map(location=centre, zoom_start=13, tiles=None)
    map.add_child(folium.TileLayer('Cartodb dark_matter'))
    map.add_child(folium.TileLayer('Cartodb Positron'))

    # 0075bf bleu B
    # bleu turquoise #00C4B3
    # tram #8c368c
    # funiculaire #95c23d

    for transport_type, lines in lines_dict.items():
        fg = folium.FeatureGroup(name=transport_type)

        # tracés des bus plus fins, et par défaut non affichés :
        if transport_type == 'Bus':
            fg = folium.FeatureGroup(name=transport_type, show=False)
            style_function = lambda x: {'color': '#00C4B3', 'weight': 1}
        elif transport_type == 'Tramway':
            style_function = lambda x : {'color' : '#0075bf', 'weight' : 3}
        elif transport_type == 'Funiculaire':
            style_function = lambda x: {'color': '#95c23d', 'weight': 3}
        elif transport_type == 'Métro':
            style_function = lambda x : {'color' : color_red_st, 'weight' : 3}

        map.add_child(fg)
        code_lignes = []

        for line in lines:
            code_ligne = line['properties']['code_ligne']
            if code_ligne not in code_lignes:
                code_lignes.append(code_ligne)
                gjson = folium.features.GeoJson(line['geometry'],
                                                style_function = style_function)
                fg.add_child(gjson)

    folium.LayerControl().add_to(map)

    filename = 'data_grand_lyon/map_all_traces.html'
    map.save(filename)

    return filename


def get_passages_tram():
    """ Récupère les prochains passages de tramway depuis l'API du Grand Lyon
        Retourne un DataFrame"""

    # API prochains passages en temps réel
    link_passages = "https://download.data.grandlyon.com/ws/rdata/tcl_sytral.tclpassagearret/all.json?maxfeatures=-1&start=1"
    r_passages = requests.get(link_passages, auth=HTTPBasicAuth(USERNAME, PASSWORD))
    passages = pd.json_normalize(r_passages.json(), record_path = 'values')

    # insertion timestamp
    request_time = dt.datetime.now(pytz.timezone('Europe/Paris')).replace(microsecond=0)
    timestamp = [request_time for i in range(passages.shape[0])]
    s = pd.Series(timestamp, name = 'timestamp')
    passages.insert(0, 'timestamp', s)

    # correction trams
    def correct_trams(row):
        if ('T1' in row['ligne']) and ('Mermoz' in row['direction']):
            return 'T6'
        elif ('T1' in row['ligne']) and ('Perrache' in row['direction']):
            return 'T2'
        elif ('T1' in row['ligne']) and ('Meyzieu' in row['direction']):
            return 'T3'
        elif ('T4' in row['ligne']) and ('Gare Part-Dieu' in row['direction']):
            return 'T3'
        elif ('T4' in row['ligne']) and ('Meyzieu' in row['direction']):
            return 'T3'
        else:
            return row['ligne']

    passages['ligne'] = passages.apply(correct_trams, axis=1)

    # nettoyage passages
    passages['direction'] = passages['direction'].apply(str.strip)
    passages['ligne'] = passages['ligne'].apply(lambda x : x.replace('A', ''))
    passages = passages[~((passages['direction'] == 'Porte des Alpes') & (passages['ligne'] == 'T2'))]
    passages = passages[~((passages['direction'] == 'Perrache') & (passages['ligne'] == 'T2'))]
    passages = passages[~((passages['direction'] == 'Grange Blanche') & (passages['ligne'] == 'T2'))]

    # filtrage : tram uniquement
    lignes_tram = ['T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7']
    passages = passages[passages.ligne.isin(lignes_tram)]

    # filtrage colonnes
    passages.drop(['coursetheorique', 'gid', 'idtarretdestination', 'last_update_fme', 'type'], axis=1, inplace=True)
    # transformation en format date
    passages['heurepassage'] = pd.to_datetime(passages['heurepassage'])

    # index à 0
    passages.reset_index(inplace=True, drop=True)

    # API points d'arrêt (= stations)
    link_stations = "https://download.data.grandlyon.com/wfs/rdata?SERVICE=WFS&VERSION=2.0.0&request=GetFeature&typename=tcl_sytral.tclarret&outputFormat=application/json; subtype=geojson&SRSNAME=EPSG:4171&startIndex=0"
    r_stations = requests.get(link_stations)
    points_arret = pd.json_normalize(r_stations.json(), record_path = 'features')

    # filtrage & reformatage
    points_arret['properties.id'] = points_arret['properties.id'].astype('int64')
    points_arret.drop(['type', 'properties.pmr', 'properties.ascenseur', 'properties.desserte', 'properties.gid', 'properties.escalator', 'properties.last_update', 'properties.last_update_fme', 'geometry.type'], axis=1, inplace=True)
    points_arret['properties.nom'] = points_arret['properties.nom'].apply(lambda x : x.replace('St', 'Saint'))
    passages = passages.merge(points_arret, how='left', left_on='id', right_on='properties.id')
    passages = passages[['timestamp', 'ligne', 'id', 'direction', 'properties.nom', 'delaipassage', 'heurepassage', 'geometry.coordinates']]

    def get_concat(row):
        concat = f"{row['ligne']} - {row['direction']} - {str(row['id'])}"
        return concat

    try:
        tmp = passages.apply(get_concat, axis=1)
        passages['concat'] = tmp
    except ValueError:
        print(tmp.shape)

    passages = passages.sort_values(['concat', 'heurepassage']).drop_duplicates(subset=['concat'])
    passages['delaipassage'].replace(to_replace='Proche', value='0 min', inplace = True)

    passages.reset_index(inplace=True, drop=True)

    return passages


def get_json_tram():
    """ Récupère les tracés des tramways depuis l'API du Grand Lyon
        Retourne des données au format JSON"""

    link_tram = "https://download.data.grandlyon.com/wfs/rdata?SERVICE=WFS&VERSION=2.0.0&request=GetFeature&typename=tcl_sytral.tcllignetram_2_0_0&outputFormat=application/json; subtype=geojson&SRSNAME=EPSG:4171"
    r_tram = requests.get(link_tram)
    traces_tram = pd.json_normalize(r_tram.json())['features'][0]

    # harmonisation orthographe terminus
    tram_terminus = ['Debourg', 'Hôtel de Région Montrochet', 'IUT Feyssine', 'Saint-Priest Bel Air',
                     'La Doua-Gaston Berger', 'Hôpital Feyzin Vénissieux', 'Eurexpo', 'Grange Blanche',
                     'Meyzieu les Panettes', 'Gare Part-Dieu', 'Décines-O.L.Vallée',
                     'Vaulx-en-Velin La Soie', 'Hôpitaux Est-Pinel']

    dico_correction = {'H.' : 'Hôtel',
                     'Hôp.' : 'Hôpital',
                     'G.Berger' : 'Gaston Berger',
                     'St' : 'Saint',
                     'Vaulx' : 'Vaulx-en-Velin'}

    for tram in traces_tram:
        origine = tram['properties']['nom_origine']
        destination = tram['properties']['nom_destination']

        for word in origine.split():
            if word in dico_correction:
                tram['properties']['nom_origine'] = tram['properties']['nom_origine'].replace(word, dico_correction[word])

        for word in destination.split():
            if word in dico_correction:
                tram['properties']['nom_destination'] = tram['properties']['nom_destination'].replace(word, dico_correction[word])

        for terminus in tram_terminus:
            if fuzz.partial_ratio(tram['properties']['nom_destination'], terminus) >= 80:
                tram['properties']['nom_destination'] = terminus

    return traces_tram


def get_map_tram(df, traces_tram, ligne, terminus):

    p = df[df['ligne'] == ligne]
    p['fuzz_ratio'] = p['properties.nom'].apply(lambda x : fuzz.partial_ratio(x, terminus))
    p = p[(p['direction'] == terminus) | (p['fuzz_ratio'] >= 77)]
    p.reset_index(inplace=True)

    request_time = p['timestamp'].unique()[0]
    tram_terminus = list(df['direction'].unique())

    # 'centre' géographique de chaque ligne
    centre_lignes = {'T1' : [4.842535168843551, 45.75540611072912][::-1],     # Guillotière
                     'T2' : [4.859213452134834, 45.74009698588613][::-1],     # Jet d'Eau
                     'T3' : [4.910450819111944, 45.758460196002034][::-1],    # Bel Air les Brosses
                     'T4' : [4.859213452134834, 45.74009698588613][::-1],     # Jet d'Eau
                     'T5' : [4.904503423384204, 45.73496753878445][::-1],     # Boutasse C. Rousset
                     'T6' : [45.727601206367986, 4.862018242655342],          # moyenne du tracé
                     'T7' : [45.77648840600608, 4.972809071935217]}           # moyenne du tracé


    # AFFICHAGE TRACES + STATIONS

    # centre automatique sur la ligne choisie
    for tram in centre_lignes:
        if tram == ligne:
            centre = centre_lignes[tram]

    map_tram_tr = folium.Map(location=centre, zoom_start=14)
    map_tram_tr.add_child(folium.TileLayer("cartodbpositron"))

    # ajout traces
    for line in traces_tram:
        ligne_segment = line['properties']['ligne']
        if ligne_segment == ligne:
            gjson = folium.features.GeoJson(line['geometry'],
                                            style_function = lambda x: {'color': color_red_st,
                                                                        'weight': 3})
            map_tram_tr.add_child(gjson)
            break

    # ajout des stations sur la carte
    for i in range(len(p)):
        loc = p.loc[i]['geometry.coordinates'][::-1]
        nom = p.loc[i]['properties.nom']
        delai = p.loc[i]['delaipassage']
        ts = p.loc[i]['timestamp']
        text_actu = f"Dernière actualisation à {request_time.strftime('%X')}"

        tip = folium.Tooltip(f"<b>{nom}</b> <br> En direction de {terminus} <br> Prochain passage : {delai} <br> {text_actu}")

        # noms des terminus
        for term in tram_terminus:
            if fuzz.partial_ratio(nom, term) >= 80:
                icon = folium.DivIcon(html=('<svg height="100" width="300">'
                                        f'<text x="15" y="15" fill="black" font-weight="bold">{nom}</text>'
                                        '</svg>'))
                folium.Marker(
                    location = loc,
                    icon = icon
                    ).add_to(map_tram_tr)

        # ronds pour stations
        icon = folium.plugins.BeautifyIcon(icon_shape='circle-dot',
                                            border_color= color_red_st,
                                            border_width=6)

        folium.Marker(
            location = loc,
            tooltip = tip,
            icon = icon
            ).add_to(map_tram_tr)


    filename = "data_grand_lyon/map_tram_tr.html"
    map_tram_tr.save(filename)

    return filename


def get_df_parcs_relais():
    """ Lit le csv parcs relais, retourne un DataFrame nettoyé"""

    df_parc = pd.read_csv('data_grand_lyon/parcs_relais.csv', index_col=[0])

    # filtrage & reformatage
    df_parc['dateTime'] = df_parc['timestamp'].astype('datetime64[ns]')
    df_parc['jour'] = df_parc['dateTime'].dt.weekday
    dayOfWeek={0:'Lundi', 1:'Mardi', 2:'Mercredi', 3:'Jeudi', 4:'Vendredi', 5:'Samedi', 6:'Dimanche'}
    df_parc['jour'] = df_parc['dateTime'].dt.dayofweek.map(dayOfWeek)
    df_parc['heure'] = df_parc['dateTime'].dt.hour
    df_parc['periode'] = df_parc['heure'].apply(lambda x: 'Matin' if x < 12 else 'Apres_midi')
    df_parc['nom'] = df_parc['nom'].apply(lambda x : x.replace('Parc Relais TCL ', ''))
    df_parc['nom'] = df_parc['nom'].apply(lambda x : x.replace('Hopital', 'Hôp.'))
    parcs_nan = ['Feyssine', 'Gare de Vénissieux', 'Grézieu la Varenne', 'Porte des Alpes',
                'Irigny-Yvours', 'Oullins La Saulaie Nord', 'Porte de Lyon']
    df_parc = df_parc[~df_parc['nom'].isin(parcs_nan)]
    df_parc.reset_index(inplace=True)
    df_parc['taux_remplissage'] = (df_parc['capacite'] - df_parc['nb_tot_place_dispo'])/df_parc['capacite'] * 100

    def parc_fermeture(row):
        if row['heure'] <= 5 and row['nb_tot_place_dispo'] == 0:
            return 0
        elif (row['nom'] == 'Laurent Bonnevay' or row['nom'] == 'Gorge de Loup') and (row['jour'] == 'Dimanche'):
            return 0
        elif row['nom'] == 'Meyzieu les Panettes' and (row['jour'] == 'Samedi' or row['jour'] == 'Dimanche'):
            return 0
        return row['taux_remplissage']

    df_parc['taux_remplissage'] = df_parc.apply(parc_fermeture, axis=1)

    df_parc.drop(columns=['gid', 'horaires', 'id', 'last_update', 'last_update_fme',
                          'p_surv', 'place_handi'], inplace=True)

    return df_parc


def get_graph_pr_tous(df_parc, jour):
    """ Génère le graphe : évolution animée du remplissage
        de tous les parcs relais pour un jour
        Retourne fig """

    df_day_parc = df_parc[(df_parc['jour'] == jour)]
    df_day_parc1 = pd.pivot_table(df_day_parc, index = ['nom', "heure"], aggfunc = "mean")
    df_day_parc1.reset_index(inplace=True)

    fig = px.bar(df_day_parc1, x="nom", y='taux_remplissage', color = "nom", animation_frame="heure",
                labels={"taux_remplissage": "",
                        "nom": ""},
                )
    fig.update_layout(margin=dict(l=70, r=40, t=70, b=200),
                      title_text=f"<b>Évolution du remplissage (%) des parcs relais un {jour.lower()} (cliquez sur play)</b>", title_x=0.5, title_font_size=20,
                      xaxis = dict(tickfont = dict(size=16)),
                      yaxis = dict(tickfont = dict(size=16)),
                      height = 700,
                      showlegend=False)
    fig['layout']['updatemenus'][0]['pad']=dict(r= 20, t= 160)
    fig['layout']['sliders'][0]['pad']=dict(r= 20, t= 150)

    fig.update_yaxes(range=[0, 100])

    return fig


def get_graph_pr(df_parc, parc, jour):
    """"""

    df_day_parc = df_parc[(df_parc['jour'] == jour)]
    df_day_parc = df_day_parc[(df_day_parc['nom'] == parc)]
    df_day_parc1 = pd.pivot_table(df_day_parc, index = "heure", values = "taux_remplissage")
    df_day_parc1.reset_index(inplace=True)

    fig = px.line(df_day_parc1, x="heure", y='taux_remplissage',
                labels={"taux_remplissage": "",
                        "heure": "Heure"},
                        height=550, color_discrete_sequence=[color_red_st])
    fig.update_layout(title_text=f"<b>Évolution du remplissage (%) du parc relais {parc} un {jour.lower()}</b>", title_x=0.5, title_font_size=20,
                      xaxis = dict(tickfont = dict(size=14)),
                      yaxis = dict(tickfont = dict(size=14)))
    fig.update_yaxes(range=[0, 100])
    fig.update_xaxes(range=[0, 23], dtick=1)

    return fig


def get_df_velov():
    """ Lit le csv velov, retourne un DataFrame nettoyé"""

    df_velov = pd.read_csv('data_grand_lyon/velov_concat.csv')

    df_velov['taux_remplissage'] = (df_velov['available_bike_stands']/df_velov['bike_stands'])*100
    df_velov['dateTime'] = df_velov['timestamp'].astype('datetime64[ns]')
    df_velov['jour'] = df_velov['dateTime'].dt.weekday
    dayOfWeek={0:'Lundi', 1:'Mardi', 2:'Mercredi', 3:'Jeudi', 4:'Vendredi', 5:'Samedi', 6:'Dimanche'}
    df_velov['jour'] = df_velov['dateTime'].dt.dayofweek.map(dayOfWeek)
    df_velov['heure'] = df_velov['dateTime'].dt.hour

    df_velov.drop(columns=['Unnamed: 0',"availabilitycode", "number", "available_bikes", "available_bike_stands",
                      "bike_stands", "code_insee", "nmarrond", "fill_rate_percent", "gid", "lat", "lng", "lon"], inplace=True)

    return df_velov


def get_graph_velov_communes(df_velov, jour):

    df_day = df_velov[(df_velov['jour'] == jour)]

    df_day3 = pd.pivot_table(df_day, index = ['commune', "heure"], aggfunc = "mean")
    df_day3.reset_index(inplace=True)

    fig = px.bar(df_day3, x="commune", y='taux_remplissage', color = "commune", animation_frame="heure",
                labels={"taux_remplissage": "",
                        "commune": ""},
                    width=1200, height=800)
    fig.update_layout(title_text=f"<b>Évolution du remplissage (%) des stations Vélo'v, un {jour.lower()}</b> (cliquez sur 'play' sous le graphe)", title_x=0.5, title_font_size=20,
                      xaxis = dict(tickfont = dict(size=14)),
                      yaxis = dict(tickfont = dict(size=14)),
                      showlegend=False)
    fig['layout']['updatemenus'][0]['pad']=dict(r= 20, t= 200)
    fig['layout']['sliders'][0]['pad']=dict(r= 20, t= 180,)

    fig.update_yaxes(range=[0, 100])

    return fig


def get_graph_velov_unecommune(df_velov, jour, commune):

    df_day = df_velov[df_velov['jour'] == jour]
    df_day = df_velov[df_velov['commune'] == commune]

    df_day1 = pd.pivot_table(df_day, index = ['name', "heure"], values='taux_remplissage', aggfunc = "mean")
    df_day1.reset_index(inplace=True)

    fig = px.bar(df_day1, x="name", y='taux_remplissage', animation_frame="heure", color="taux_remplissage",
                color_continuous_scale = px.colors.sequential.Blues, range_color=[0, 100],
                labels={"taux_remplissage": "",
                        "name": ""},
                width=1200, height=700)

    fig.update_layout(margin=dict(l=70, r=70, t=70, b=200),
                      title_text=f"<b>Évolution du remplissage (%) des stations Vélo'v de {commune} un {jour.lower()}</b>",
                      title_x=0.5, title_font_size=20,
                      xaxis = dict(tickfont = dict(size=16)),
                      yaxis = dict(tickfont = dict(size=16)),
                      height = 700,
                      showlegend=False,
                      coloraxis_showscale=False)
    fig['layout']['updatemenus'][0]['pad']=dict(r= 20, t= 150)
    fig['layout']['sliders'][0]['pad']=dict(r= 20, t= 140,)

    fig.update_yaxes(range=[0, 100])

    return fig


def get_graph_velov_unestation(df_velov, jour, commune, station):

    df_day = df_velov[(df_velov['jour'] == jour)]
    df_day = df_day[(df_day['commune'] == commune)]
    df_day = df_day[(df_day['name'] == station)]
    df_day2 = pd.pivot_table(df_day, index = ["heure"], aggfunc = "mean")
    df_day2.reset_index(inplace=True)

    fig = px.line(df_day2, x="heure", y='taux_remplissage',
                    labels={"taux_remplissage": "",
                            "heure": "Heures"},
                    color_discrete_sequence=[color_red_st])
    fig.update_layout(margin=dict(l=70, r=70, t=70, b=200),
                      title_text=f"<b>Évolution du remplissage (%) de la station Vélo'v {station} un {jour.lower()}</b>",
                      title_x=0.5, title_font_size=20,
                      xaxis = dict(tickfont = dict(size=16)),
                      yaxis = dict(tickfont = dict(size=16)),
                      width=1200, height = 700,
                      showlegend=False,)
    fig.update_yaxes(range=[0, 103])
    fig.update_xaxes(range=[0, 23], dtick=1)

    return fig
