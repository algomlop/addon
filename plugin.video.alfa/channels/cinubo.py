# -*- coding: utf-8 -*-
# -*- Channel Cinubo -*-
# -*- Created for Alfa Addon -*-
# -*- By the Alfa Development Group -*-
#
# ESTADO DEL CANAL (primer borrador, basado en la home logueada):
#   CONFIRMADO en la home:
#     - Rutas del menú: /peliculas /series /animes /novedades /sagas /listas /calendario /mi-biblioteca /solicitudes
#     - Fichas: /p/<id> (película), /s/<id> (serie), /a/<id> (anime); id de 6 caracteres
#     - Tarjeta: <div class="media-item"> con <a href="...ficha"> y <img alt="título" ...>
#     - Sesión: Laravel (meta csrf-token); logueado => existe id="profile-button" en la cabecera
#     - Campos de cada "post" (Alpine): id, link, title, poster, cover, description, vote_average, type
#       (movie|serie|anime), hasTrailer, trailer, bookmark{favorite,following,viewed,pending,collection}
#   PENDIENTE (marcado con TODO): endpoints JSON de la home/listados/búsqueda, paginación,
#     ficha de película/serie/anime, episodios y enlaces de vídeo.

import sys
PY3 = False
if sys.version_info[0] >= 3: PY3 = True; unicode = str; unichr = chr; long = int; _dict = dict

from lib import AlfaChannelHelper
if not PY3: _dict = dict; from AlfaChannelHelper import dict
from AlfaChannelHelper import DictionaryAllChannel
from AlfaChannelHelper import re, traceback
from AlfaChannelHelper import Item, servertools, scrapertools, jsontools, get_thumb, config, logger, filtertools, autoplay, renumbertools

from platformcode.platformtools import dialog_notification, itemlist_refresh, show_channel_settings

IDIOMAS = AlfaChannelHelper.IDIOMAS_T
list_language = list(set(IDIOMAS.values()))
list_quality_movies = AlfaChannelHelper.LIST_QUALITY_MOVIES
list_quality_tvshow = AlfaChannelHelper.LIST_QUALITY_TVSHOW
list_quality = list_quality_movies + list_quality_tvshow
list_servers = AlfaChannelHelper.LIST_SERVERS

cf_assistant = True if AlfaChannelHelper.IS_ASSISTANT_INSTALLED else False
forced_proxy_opt = None
debug = config.get_setting('debug_report', default=False)

canonical = {
             'channel': 'cinubo',
             'host': config.get_setting("current_host", 'cinubo', default=''),
             'host_alt': ["https://cinubo.com/"],
             'host_black_list': [],
             'pattern': r'<link\s*rel="canonical"\s*href="([^"]+)"',
             'set_tls': True, 'set_tls_min': False, 'forced_proxy_ifnot_assistant': forced_proxy_opt,
             'retries_cloudflare': -1 if cf_assistant else 1,
             'retry_alt': False, 'CF_proxy_alt': False, 'canonical_check': False,
             'CF': False, 'CF_test': True, 'alfa_s': True, 'renumbertools': False,
             'data_js': '', 'domains_test': 0, 'Plan_B': True
            }
host = canonical['host'] or canonical['host_alt'][0]
_silence = config.get_setting('silence_mode', channel=canonical['channel'])

timeout = (5, 20)
kwargs = {}
movie_path = "p/"
tv_path = 's/'
anime_path = 'a/'
language = []
url_replace = []
plot = 'Si no ves contenido, revisa las [COLOR orange][B]cookies de sesión[/B][/COLOR] en la configuración del canal'

# Marcador de sesión iniciada: solo aparece en la cabecera de la web logueada
logged_marker = 'id="profile-button"'
patron_csrf = r'<meta\s+name="csrf-token"\s+content="([^"]+)"'

# TODO: confirmar con la pestaña Red del navegador (F12) la URL JSON que usa la búsqueda (searchModal)
# y la que usa la home (homePostsSection). Mientras estén vacías, la búsqueda devuelve [].
search_url = ''

finds = {'find': dict([('find_all', [{'tag': ['div'], 'class': ['media-item']}])]),
         'categories': {},
         'search': {},
         'get_language': {},
         'get_language_rgx': '',
         'get_quality': {},
         'get_quality_rgx': '',
         'next_page': {},
         'next_page_rgx': [],                                                    # TODO: paginación sin confirmar
         'last_page': {},
         'year': {},
         'season_episode': {},
         'seasons': {},                                                          # TODO: ficha de serie
         'season_num': {},
         'seasons_search_num_rgx': '',
         'seasons_search_qty_rgx': '',
         'season_url': host,
         'episode_url': '',
         'episodes': {},                                                         # TODO: ficha de serie
         'episode_num': [],
         'episode_clean': [],
         'plot': {},
         'findvideos': {},                                                       # TODO: ficha de película/episodio
         'title_clean': [[r'(?i)\s*\(\d{4}\)', ''],
                         [r'[\(|\[]\s*[\)|\]]', '']],
         'quality_clean': [],
         'language_clean': [],
         'url_replace': [],
         'controls': {'duplicates': [], 'min_temp': False, 'url_base64': False, 'add_video_to_videolibrary': True, 'cnt_tot': 20,
                      'get_lang': False, 'reverse': False, 'videolab_status': True, 'tmdb_extended_info': True, 'seasons_search': False,
                      'IDIOMAS_TMDB': {0: 'es', 1: 'ja', 2: 'es'}, 'jump_page': False, 'timer': 4.5},
         'timeout': timeout}
AlfaChannel = DictionaryAllChannel(host, movie_path=movie_path, tv_path=tv_path, canonical=canonical, finds=finds,
                                   idiomas=IDIOMAS, language=language, list_language=list_language, list_servers=list_servers,
                                   list_quality_movies=list_quality_movies, list_quality_tvshow=list_quality_tvshow,
                                   channel=canonical['channel'], actualizar_titulos=True, url_replace=url_replace, debug=debug)
host_save = host

""" ESTADO DE SESIÓN """
# El login de Cinubo lanza un captcha (Turnstile) que un addon no puede resolver, por lo que la sesión se
# obtiene iniciando sesión en el navegador y copiando las cookies al ajuste 'external_cookies' del canal
# (formato dominio:nombre¡valor;nombre¡valor...).
account = config.get_setting("logged", channel=canonical['channel'])
csrf = ''
_warned = False


def mainlist(item):
    logger.info()

    itemlist = []

    autoplay.init(item.channel, list_servers, list_quality)

    itemlist.append(Item(channel=item.channel, action="list_all", title="Películas", url=AlfaChannel.urljoin(host, "peliculas"),
                         thumbnail=get_thumb("channels_movie.png"), c_type="peliculas", text_bold=True, plot=plot))

    itemlist.append(Item(channel=item.channel, action="list_all", title="Series", url=AlfaChannel.urljoin(host, "series"),
                         thumbnail=get_thumb("channels_tvshow.png"), c_type="series", text_bold=True, plot=plot))

    itemlist.append(Item(channel=item.channel, action="list_all", title="Animes", url=AlfaChannel.urljoin(host, "animes"),
                         thumbnail=get_thumb("anime", auto=True), c_type="animes", text_bold=True, plot=plot))

    itemlist.append(Item(channel=item.channel, action="list_all", title=" - [COLOR paleturquoise]Novedades[/COLOR]",
                         url=AlfaChannel.urljoin(host, "novedades"), thumbnail=get_thumb("newest", auto=True), c_type="novedades",
                         plot=plot))

    # TODO: /sagas y /listas (colecciones) cuando se vea su marcado
    # itemlist.append(Item(channel=item.channel, action="list_all", title=" - [COLOR paleturquoise]Sagas[/COLOR]", url=host + "sagas"))
    # itemlist.append(Item(channel=item.channel, action="list_all", title=" - [COLOR paleturquoise]Listas[/COLOR]", url=host + "listas"))

    if account:
        itemlist.append(Item(channel=item.channel, action="list_all", title="    - [COLOR orange]Pendientes[/COLOR]",
                             url=AlfaChannel.urljoin(host, "mi-biblioteca?category=pending"), extra="biblioteca",
                             thumbnail=get_thumb("videolibrary.png"), c_type="biblioteca", plot=plot))

        itemlist.append(Item(channel=item.channel, action="list_all", title="    - [COLOR orange]Siguiendo[/COLOR]",
                             url=AlfaChannel.urljoin(host, "mi-biblioteca?category=following"), extra="biblioteca",
                             thumbnail=get_thumb("favorites.png"), c_type="biblioteca", plot=plot))

    itemlist.append(Item(channel=item.channel, title="Buscar...", action="search", url=host,
                         thumbnail=get_thumb("search.png"), plot=plot))

    if not account:
        itemlist.append(Item(channel=item.channel, action="configuracion", url="", text_bold=True,
                             title="[COLOR dodgerblue]Configura tus cookies de sesión de Cinubo...[/COLOR]",
                             thumbnail=get_thumb("setting_0.png")))
    else:
        itemlist.append(Item(channel=item.channel, action="configuracion", title="Configurar canal",
                             thumbnail=get_thumb("setting_0.png")))

    itemlist = renumbertools.show_option(item.channel, itemlist, status=canonical.get('renumbertools', False))

    itemlist = filtertools.show_option(itemlist, item.channel, list_language, list_quality_tvshow, list_quality_movies)

    autoplay.show_option(item.channel, itemlist)

    return itemlist


def configuracion(item):

    ret = show_channel_settings()
    if account: itemlist_refresh()

    return item


def list_all(item):
    logger.info()

    findS = finds.copy()

    return AlfaChannel.list_all(item, matches_post=list_all_matches, finds=findS, **kwargs)


def list_all_matches(item, matches_int, **AHkwargs):
    logger.info()

    matches = []
    findS = AHkwargs.get('finds', finds)

    for elem in matches_int:
        elem_json = {}
        #logger.error(elem)

        try:
            if isinstance(elem, _dict):
                # Respuesta JSON (campos confirmados en los bindings de la home y del buscador)
                url = elem.get('link', '')
                title = elem.get('title', '')
                thumb = elem.get('poster', '')
                ptype = elem.get('type', '')
                post_id = str(elem.get('id', '') or '')
            else:
                # Tarjeta HTML: <div class="media-item"><a href=".../p/xxxxxx"><img alt="Título" ...>
                a = elem.find('a', href=True)
                if not a: continue
                img = a.find('img')
                url = a.get('href', '')
                title = img.get('alt', '') if img else ''
                if not title and elem.find('h4'): title = elem.find('h4').get_text(strip=True)
                thumb = (img.get('data-src', '') or img.get('src', '')) if img else ''
                ptype = ''
                post_id = ''

            if not url or not title: continue
            url = AlfaChannel.urljoin(host, url)

            # El tipo se deduce de la ruta de la ficha: /p/ película, /s/ serie, /a/ anime
            if not ptype:
                ptype = 'movie' if '/%s' % movie_path in url else 'anime' if '/%s' % anime_path in url else 'serie'
            elem_json['mediatype'] = 'movie' if ptype == 'movie' else 'tvshow'

            if item.c_type == 'peliculas' and ptype != 'movie': continue
            if item.c_type == 'series' and ptype != 'serie': continue
            if item.c_type == 'animes' and ptype != 'anime': continue

            elem_json['title'] = title.strip()
            elem_json['url'] = url
            elem_json['thumbnail'] = thumb
            elem_json['quality'] = ''
            if post_id: elem_json['info'] = {post_id: post_id}

        except Exception:
            logger.error(elem)
            logger.error(traceback.format_exc())
            continue

        matches.append(elem_json.copy())

    return matches


def seasons(item):
    logger.info()

    # TODO: pendiente de ver la ficha de una serie/anime (/s/xxxxxx, /a/xxxxxx)
    logger.error('Cinubo: seasons() pendiente de implementar')

    return []


def episodios(item):
    logger.info()

    # TODO: pendiente de ver la ficha de una serie/anime
    return []


def episodesxseason(item, **AHkwargs):
    logger.info()

    # TODO: pendiente de ver la ficha de una serie/anime
    return []


def findvideos(item):
    logger.info()

    # TODO: pendiente de ver la ficha de una película (/p/xxxxxx) y de un episodio
    logger.error('Cinubo: findvideos() pendiente de implementar')

    return []


def play(item):

    devuelve = servertools.findvideosbyserver(item.url, item.server)

    if devuelve:
        item.url = devuelve[0][1]
    else:
        devuelve = servertools.findvideos(item.url, True)
        if devuelve:
            item.url = devuelve[0][1]
            item.server = devuelve[0][2]
    item.thumbnail = item.contentThumbnail

    return [item]


def actualizar_titulos(item):
    logger.info()
    # Llamamos al método que actualiza el título con tmdb.find_and_set_infoLabels

    return AlfaChannel.do_actualizar_titulos(item)


def search(item, texto, **AHkwargs):
    logger.info()
    kwargs.update(AHkwargs)

    try:
        texto = texto.replace(" ", "+")

        if len(texto) < 2:                                                       # El buscador web exige 2 caracteres mínimo
            return []

        if not search_url:
            logger.error('Cinubo: search() pendiente de confirmar el endpoint de búsqueda')
            return []

        item.url = search_url % texto
        item.c_type = 'search'
        item.texto = texto

        return list_all(item)

    # Se captura la excepción, para no interrumpir al buscador global si un canal falla
    except Exception:
        for line in sys.exc_info():
            logger.error("%s" % line)
        return []


""" SESIÓN """
def check_login_status(data):
    global account, csrf

    if not isinstance(data, str) or not data:
        return account

    account = logged_marker in data
    if account:
        csrf = scrapertools.find_single_match(data, patron_csrf) or csrf
    if account != config.get_setting("logged", channel=canonical['channel']):
        config.set_setting("logged", account, channel=canonical['channel'])

    return account


def agrupa_datos(url, post=None, referer=True, json=False, hide_infobox=False):
    global _warned

    headers = {'Referer': host}
    if isinstance(referer, str):
        headers.update({'Referer': referer})
    if csrf and post:
        headers['X-CSRF-TOKEN'] = csrf
        headers['X-Requested-With'] = 'XMLHttpRequest'

    page = AlfaChannel.create_soup(url, post=post, headers=headers, ignore_response_code=True, timeout=timeout,
                                   soup=False, json=False, canonical=canonical, hide_infobox=hide_infobox,
                                   alfa_s=not canonical.get('print_DEBUG', False))

    if not page.sucess:
        return {} if json else ''

    if json:
        if not page.json and page.data:
            page.json = jsontools.load(page.data, silence=True)
        return page.json

    data = page.data
    if PY3 and isinstance(data, bytes):
        data = "".join(chr(x) for x in bytes(data))

    if not check_login_status(data) and not _warned:
        _warned = True
        if not _silence:
            dialog_notification("Sesión no iniciada en Cinubo", "Revise las cookies en la configuración del canal", sound=False)

    return data
