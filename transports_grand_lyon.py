import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import json
import datetime as dt
import folium
from folium.plugins import MarkerCluster
import streamlit.components.v1 as components
from streamlit_option_menu import option_menu
from fuzzywuzzy import fuzz
import time
import fonctions as fc


#Paramétrage
st.set_page_config(
     page_title="Transports du Grand Lyon",
     page_icon=":train:",
     layout="wide",
     initial_sidebar_state="expanded")
color_red_st = '#FF4B4B'        # rouge par défaut sur Streamlit
map_height = 800
st.markdown(
        f"""
<style>
    # .reportview-container .main .block-container{{
    #     max-width: 90%;
    #     padding-top: 5rem;
    #     padding-right: 5rem;
    #     padding-left: 5rem;
    #     padding-bottom: 5rem;
    # }}
    img{{
    	max-width:40%;
    	margin-bottom:0px;
    }}
    p{{
        font-size: x-large;
    }}
    li{{
        font-size:x-large;
    }}
    h1{{
        padding-right: 5rem;
        padding-left: 5rem;
        padding-bottom: 5rem;
    }}
    h4{{
        padding-bottom: 2rem;
    }}
</style>
""",
        unsafe_allow_html=True,
    )


# Sidebar
with st.sidebar:
    options = ["Accueil", "Vélo'v : analyse", "Vélo'v en temps réel", "Parcs relais", "Horaires des tramways", "À propos"]
    menu_title = "Les transports du Grand Lyon"
    choice = option_menu(menu_title=None, options=options, icons=['house', 'graph-up', 'bicycle', 'building', 'watch', 'info-circle'],)

# Body
if choice == "Accueil":
    #Titre Général
    st.markdown("<h1 style='text-align: center; color: #FF4B4B;'>LES TRANSPORTS DU GRAND LYON</h1>", unsafe_allow_html=True)

    st.image('images/Funiculaire-h.jpg')
    components.html("<p><a style='float: right; font-size:small; font-family: arial; color: #5b5b5b;' href=\"https://commons.wikimedia.org/wiki//File:Funiculaire.jpg\">Photo par Magicludovic, CC BY-SA 3.0</a></p>")

    st.markdown("#### Bienvenue sur ce dashboard interactif sur les moyens de transport dans l’agglomération lyonnaise.")
    st.markdown("Vous trouverez diverses informations sur l’usage des Vélo’v, le réseau de pistes cyclables,\
            le tramway, des suggestions d’itinéraires piétons…")
    st.markdown("Mais tout d’abord quelques chiffres :")
    st.markdown("• Lyon est la 3ème ville de France, près de 1,4 millions de personnes vivent dans son agglomération, \
        et sa superficie s’étend sur plus de 500 km², ce qui explique l’importance et l’étendue de son réseau de transport.")
    st.markdown("• Le réseau de bus et trolleybus comprend 120 lignes, pour une longueur totale d’environ 2500 km.")
    st.markdown("• Le réseau de métro comprend 4 lignes, qui totalisent 40 stations et 32 kms de voies.\
        Plus de 200 millions de voyages sont effectués chaques années, et représentent 44% de la fréquentation du réseau TCL.")
    st.markdown("• Le réseau de tramway comprend 7 lignes, d’une longueur totale de 76,7 km.")
    st.markdown("• Les parcs relais sont au nombre de 22 et offrent près de 7500 places de stationnement dans la périphérie lyonnaise.")
    st.markdown("• Les pistes cyclables représentent actuellement 540 kms sur le territoire.\
                Les “voies lyonnaises” dont les travaux viennent de démarrer, vont ajouter près de 400 km\
                  de voies cyclables aménagées dans toute l'agglomération. \
                 Un réseau très ambitieux, dont la construction doit s'étaler jusqu'en 2030.")
    st.text("")
    st.text("")
    st.markdown("#### La carte ci-dessous montre l'ensemble du réseau de transports en commun.")
    st.markdown("Cliquez sur les carrés en haut à droite de la carte pour sélectionner les moyens de transport affichés.")


    file_traces = open(fc.get_all_traces_color(), 'r', encoding='utf-8')
    components.html(file_traces.read(), height=map_height+10)


if choice == "Vélo'v : analyse":
    #Titre Général
    st.markdown("<h1 style='text-align: center; color: #FF4B4B;'>LES VÉLO'V : ANALYSE DE FRÉQUENTATION</h1>", unsafe_allow_html=True)
    st.text("")

    st.image("images/velov_Lyon_Velo'v_Station.jpg")
    components.html("<p><a style='float: right; font-size:small; font-family: arial; color: #5b5b5b;' href=\"https://commons.wikimedia.org/wiki/File:Lyon_Velo%27v_Station.jpg\">Photo par Elwood j blues, CC BY-SA 3.0</a></p>")

    st.markdown("Avec 428 stations et 5 000 vélos, Vélo’v propose aux habitants des 32 communes\
        de la Métropole de Lyon depuis le 19 maI 2005 un vélo en libre-service, disponible 24h/24 et 7j/7.\
        En janvier 2022, la Métropole dispose de 424 stations ouvertes et 4 fermées.")
    st.markdown("#### Découvrez l'évolution animée du remplissage des stations Vélo’v du 4ème arrondissement de Lyon, tout au long de la semaine (appuyez sur play sous le graphique).")

    if 'velov' not in st.session_state:
        st.session_state['velov'] = fc.get_df_velov()

    df_velov = st.session_state['velov']

    liste_jours = ['Sélectionnez un jour de la semaine', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    jour = st.selectbox('', options=liste_jours)
    st.text("")

    if jour != liste_jours[0]:
        with st.spinner('Chargement du graphique en cours...'):
            commune_choisie = "Lyon 4 ème"
            fig_velov_lyon4 = fc.get_graph_velov_unecommune(df_velov, jour, commune_choisie)
            st.plotly_chart(fig_velov_lyon4, config=dict(displayModeBar=False))

        st.text("")
        st.text("")
        # 'Mairie du 4e'
        st.markdown("## Focus sur la station Vélo'v : *Mairie du 4ème*")
        st.markdown("Nous avons décidé de faire un focus sur la station Vélo’v “Mairie du 4 ème”\
            située sur le plateau de la Croix-Rousse, et de regarder l'évolution de son remplissage un mardi, un samedi et un dimanche.")

        st.markdown("#### Mardi")
        st.markdown("Nous pouvons constater que le mardi, la station se vide entre 8h et 10h.\
            Il s’agit des heures où les personnes partent travailler.\
            Le nombre de vélos baisse fortement à 13h à l’heure du déjeuner.\
            Puis, la station se remplit progressivement à partir de 17h après la journée de travail.")
        fig_velov_mairie_m = fc.get_graph_velov_unestation(df_velov, jour='Mardi', commune=commune_choisie, station='Mairie du 4e')
        st.plotly_chart(fig_velov_mairie_m, config=dict(displayModeBar=False))

        st.markdown("#### Samedi")
        st.markdown("Le samedi, le nombre de vélos baisse fortement entre 8h et 10h en raison du marché ou des personnes partant \
            en centre-ville. La station se remplit ensuite fortement à partir de 15h pour arriver à son plein à 19h \
                lorsque les personne rentrent chez elles ou se rendent dans un bar/restaurant.")
        fig_velov_mairie_s = fc.get_graph_velov_unestation(df_velov, jour='Samedi', commune=commune_choisie, station='Mairie du 4e')
        st.plotly_chart(fig_velov_mairie_s, config=dict(displayModeBar=False))


        st.markdown("#### Dimanche")
        st.markdown("Le dimanche, nous pouvons constater que les vélos sont très peu utilisés et cela entre 9h et 18h.")
        fig_velov_mairie_d = fc.get_graph_velov_unestation(df_velov, jour='Dimanche', commune=commune_choisie, station='Mairie du 4e')
        st.plotly_chart(fig_velov_mairie_d, config=dict(displayModeBar=False))


if choice == "Vélo'v en temps réel":
    st.markdown("<h1 style='text-align: center; color: #FF4B4B;'>LES VÉLO'V : DISPONIBILITÉS EN TEMPS RÉEL</h1>", unsafe_allow_html=True)
    st.info("Pour plus de confort, nous vous invitons à fermer le volet de gauche.")
    st.markdown("##### Avec 425 stations et 5 000 vélos, Vélo’V propose aux habitants de la Métropole de Lyon\
        depuis 2005 un vélo en libre service, disponible 24h/24 et 7j/7.")
    st.markdown("#### Les deux cartes ci-dessous représentent les disponibilités des Vélo'v en temps réel.")
    st.markdown("###### Elles permettent aussi d'apprécier la répartition des stations sur l'ensemble du territoire de \
                l'agglomération.")
    st.text("")


    if 'velov_tr' not in st.session_state:
        st.session_state['velov_tr'] = fc.get_df_velov_tr()

    df_velov_tr = st.session_state['velov_tr']

    request_time = df_velov_tr['timestamp'].unique()[0]
    actu = f"Dernière actualisation à {request_time.strftime('%X')}"
    st.text(actu)

    with st.spinner('Chargement de la carte en cours...'):
        file_velov = open(fc.get_map_velov_tr(df_velov_tr), 'r', encoding='utf-8')
        components.html(file_velov.read(), height=map_height+10)


if choice == "Parcs relais":

    st.markdown("<h1 style='text-align: center; color: #FF4B4B;'>LES PARCS RELAIS</h1>", unsafe_allow_html=True)
    st.text("")
    st.text("")
    st.image('images/parcs_relais_2048px-Parking_relais_TCL_C3_Bonnevay.JPG')
    components.html("<p><a style='float:right; font-size:small; font-family: arial; color: #5b5b5b;' href=\"https://commons.wikimedia.org/wiki/File:Parking_relais_TCL_C3_Bonnevay.JPG\">Xavier Caré / Wikimedia Commons</a></p>")

    st.markdown("Les parcs relais sont des lieux de stationnement qui offrent 7500 places aux clients du réseau TCL.\
        Ils permettent aux personnes vivant en-dehors de Lyon de garer leur véhicule au prix d'un ticket de métro.")
    st.markdown("Ils sont situés à proximité directe du métro, du tramway ou d\'un centre d\'échanges TCL. \
        Les parcs relais en correspondance avec les lignes de métro sont ouverts jusqu\'à 3h du matin \
        tous les vendredis et samedis (au lieu d\'1h du matin).")

    st.markdown("Les parcs relais en chiffres :")
    st.markdown('•  Nombre total de parcs relais : 22', unsafe_allow_html=True)
    st.markdown('•  Nombre total de places : 7 324', unsafe_allow_html=True)
    st.markdown('•  Nombre total de places PMR : 180', unsafe_allow_html=True)
    st.text("")
    st.info("Pour plus de confort, nous vous invitons à fermer le volet de gauche.")
    st.markdown("#### Découvrez ci-dessous l'évolution animée de la fréquentation des parcs relais de la Métropole de Lyon tout au long de la semaine :")

    if 'parcs_relais' not in st.session_state:
        st.session_state['parcs_relais'] = fc.get_df_parcs_relais()
    df_parc = st.session_state['parcs_relais']
    liste_jours = ['Sélectionnez un jour de la semaine', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

    col1, col2 = st.columns(2)
    with col1:
        jour_choisi = st.selectbox('', options=liste_jours)
        st.text("")
        st.text("")

        if jour_choisi != liste_jours[0]:
            fig1 = fc.get_graph_pr_tous(df_parc, jour_choisi)
            st.plotly_chart(fig1, config=dict(displayModeBar=False))
            st.text("")
            st.text("")

            with col2:
                liste_parcs = sorted(list(df_parc['nom'].unique()))
                liste_parcs.insert(0, 'Sélectionnez un parc relais')
                parc_choisi = st.selectbox("", options=liste_parcs)
                st.text("")
                st.text("")
                if parc_choisi != liste_parcs[0]:
                    df_parc_choisi = df_parc[df_parc['nom'] == parc_choisi]
                    taux_unique = df_parc_choisi['taux_remplissage'].unique()
                    if len(taux_unique) <= 1 and taux_unique[0] <= 0:
                        st.error("Données non disponibles")
                    else:
                        fig2 = fc.get_graph_pr(df_parc, parc_choisi, jour_choisi)
                        st.plotly_chart(fig2, config=dict(displayModeBar=False))

    st.markdown("**Les jours de semaine,** ces graphiques montrent une nette augmentation de la fréquentation des parcs\
                à partir de 7h du matin, et une diminution vers 16h. Certains parcs restent parfois totalement saturés une bonne\
                partie de la journée ; c'est le cas notamment des parcs de Cuire, Mermoz, Meyzieu et Oullins.\
                On peut aisément imaginer que les personnes résidant en périphérie et travaillant dans Lyon\
                garent leur voiture dans ces parcs relais\
                et finissent leur trajet en transport en commun. Elles évitent ainsi de participer au congestionnement\
                du trafic dans le centre ville.")
    st.markdown("**Le samedi,** la fréquentation est moins élevée qu'en semaine. Seuls les parcs de Gorge de Loup\
                et Oullins dépassent les 80% de remplissage ; les autres parcs restant majoritairement en-dessous\
                de 40%. Par ailleurs, les horaires de fréquentation diffèrent de la semaine : les pics sont atteints\
                vers 10h puis vers 15h, indiquant que les conducteurs se déplacent pour des activités de loisir.")
    st.markdown("**Quant au dimanche,** 3 parcs sont fermés. Parmi ceux qui restent ouverts, on note une fréquentation très timide ;\
                en effet, le taux de remplissage moyen atteint tout juste les 6%.\
                Ce constat s'explique facilement par la fermeture dominicale des commerces.")
    st.text("")
    st.markdown("Ces données ont été collectées sur une semaine de janvier 2022.\
                Malheureusement, nous n’avons pas pu récupérer les données pour les parcs relais : Feyssine, Gare de Vénissieux, Grézieu la Varenne,\
                Irigny-Yvours, Oullins La Saulaie Nord, Porte des Alpes et Porte de Lyon.")


if choice == "Horaires des tramways":

    # Blabla
    st.markdown("<h1 style='text-align: center; color: #FF4B4B;'>LE TRAMWAY : HORAIRES EN TEMPS RÉEL</h1>", unsafe_allow_html=True)
    st.text("")
    st.text("")
    st.image("images/tram_1620px-Citadis_302_Lyon_T6_Challemel-Lacour_-_Artillerie.jpg")
    components.html("<p><a style='float: right; font-size:small; font-family: arial; color: #5b5b5b;' href=\"https://commons.wikimedia.org/w/index.php?curid=84308627\">Photo par Bmazerolles — Travail personnel, CC BY-SA 4.0</a></p>")

    st.markdown("Inauguré en 2001 avec ses deux premières lignes, le réseau de tramway lyonnais comporte aujourd'hui\
        7 lignes, traverse 8 communes, ainsi que 5 arrondissements lyonnais. Il relie ainsi les grands pôles économiques,\
        commerciaux et universitaires de l'agglomération lyonnaise en transportant chaque jour 300 000 voyageurs,\
        soit 17% du trafic sur le réseau TCL.")
    st.markdown("Le réseau de tramway comptabilise au total 76,7 km de ligne, sur lesquels circulent\
        103 rames qui desservent 104 stations. Depuis sa création il a bénéficié de 100% d'extension (+55km).")
    st.markdown("Prochains projets qui seront mis en service avant 2026 : T6 nord (prolongement jusqu'à la Doua), T8 (Bellecour - Part Dieu\
        T9 (Vaulx en Velin - la Doua) et T10 (Vénissieux - St Fons - Gerland)")

    st.markdown("#### La carte ci-dessous affiche les prochains passages des tramways, en temps réel.")
    st.info("Pour plus de confort, nous vous invitons à fermer le volet de gauche.")

    if 'passages' not in st.session_state:
        st.session_state['passages'] = fc.get_passages_tram()

    passages = st.session_state['passages']
    request_time = passages['timestamp'].unique()[0]

    # import des données géo tram + selectboxes (choix lignes + terminus)
    traces_tram = fc.get_json_tram()
    lignes_tram = sorted(passages['ligne'].unique())
    lignes_tram.insert(0, 'Sélectionnez une ligne de tramway')
    tram_terminus = sorted(list(passages['direction'].unique()))

    col1, col2 = st.columns(2)

    with col1:
        # Selectbox lignes de tram
        ligne = st.selectbox(label='', options=lignes_tram, index=0)
        if ligne != lignes_tram[0]:
            p = passages[passages['ligne'] == ligne]
            tram_terminus = sorted(list(p['direction'].unique()))
            tram_terminus.insert(0, 'Sélectionnez un terminus')

            with col2:
                # Selectbox terminus
                terminus = st.selectbox(label='', options=tram_terminus, index=0)

        text_actu = f"Dernière actualisation à {request_time.strftime('%X')}"
        actualisation = st.button('Actualiser les données')
        if actualisation:
            del st.session_state['passages']
        st.text(text_actu)

    # affichage de la carte
    with st.spinner('Chargement de la carte en cours...'):
        if (ligne != lignes_tram[0]) and (terminus != tram_terminus[0]):
            file_map_tram = open(fc.get_map_tram(passages, traces_tram, ligne, terminus), 'r', encoding='utf-8')
            components.html(file_map_tram.read(), height=map_height+10)


if choice == 'À propos':
    st.markdown("<h1 style='text-align: center; color: #FF4B4B;'>À PROPOS</h1>", unsafe_allow_html=True)
    st.markdown("#### Le contexte")
    st.markdown("Ce dashboard interactif a été réalisé en février 2022 dans le cadre du projet de clôture de\
             notre formation Data Analyst, effectuée en 5 mois à la Wild Code School de Lyon.\
            L’objectif était de travailler sur l’open data mise à disposition par la Métropole de Lyon,\
            et d’analyser les usages des différents moyens de transports dans l’agglomération.")
    st.markdown("Pour concevoir les cartes interactives des Vélo'V et des tramways, nous faisons appel à **différentes API**\
                qui fournissent des **données en temps réel.**\
                Quant aux graphiques, nous avons stocké des données en continu du 12 au 19 janvier 2022\
                afin de pouvoir ensuite établir des **tendances d'utilisation** des Vélo'V et des parcs relais.")
    st.text("")

    st.markdown("#### La technique")
    st.markdown("Pour réaliser ce projet, nous avons utilisé le langage **Python** et ses différentes\
                  bibliothèques dédiées à l’analyse et au traitement des données, \
                  à savoir : **Pandas, Numpy, Plotly, Folium, et GeoPandas.** \
                  Notre choix s'est porté sur **Streamlit** pour la mise en page du dashboard\
                  et son déploiement sous forme d’application web.")
    st.text("")

    st.markdown("#### Remerciements")
    st.markdown("Nous remercions notre formateur Jérémy Perret pour ses précieux conseils durant cette formation, \
        ainsi que la Métropole de Lyon et le Sytral pour l’accès aux données et différents contenus.")

    st.markdown("#### L'équipe")
    annecha, thomas, mouna = st.columns(3)
    with annecha:
        st.image('images/AC_LinkedIn.jpg')
        components.html(f"<p><a style='text-align: center; font-size:large; font-weight: bold; font-family: arial; color: {color_red_st};' href=\"https://www.linkedin.com/in/annecharlottebesse\" target=\"_blank\">Anne-Charlotte Besse</a></p>")
    with thomas:
        st.image('images/Thomas.jpg')
        components.html(f"<p><a style='text-align: center; font-size:large; font-weight: bold; font-family: arial; color: {color_red_st};' href=\"https://www.linkedin.com/in/thomas--grall\" target=\"_blank\">Thomas Grall</a></p>")
    with mouna:
        st.image('images/Mouna.png')
        components.html(f"<p><a style='text-align: center; font-size:large; font-weight: bold; font-family: arial; color: {color_red_st};' href=\"https://www.github.com/mounasb\" target=\"_blank\">Mouna Sebti</a></p>")
