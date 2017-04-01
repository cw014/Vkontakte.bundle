# -*- coding: utf-8 -*-

# Copyright (c) 2014, KOL
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the <organization> nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from urllib import urlencode
from updater import Updater
import urllib2
from StringIO import StringIO
import gzip
import HTMLParser

PREFIX_V = '/video/vkontakte'
PREFIX_M = '/music/vkontakte'
PREFIX_P = '/photos/vkontakte'

ART = 'art-default.jpg'
ICON = 'icon-default.png'
ICON_V = 'icon-video.png'
ICON_M = 'icon-music.png'
ICON_P = 'icon-photo.png'
TITLE = u'%s' % L('Title')

VK_APP_ID = 4510304
VK_APP_SECRET = 'H4uZCbIucFgmsHKprXla'
VK_APP_SCOPE = 'audio,video,groups,friends'
VK_VERSION = '5.5'#'5.24'
VK_LIMIT = 50


###############################################################################
# Init
###############################################################################

def Start():

    HTTP.CacheTime = CACHE_1HOUR
    ValidateAuth()


def ValidatePrefs():
    Dict.Reset()

    if (ValidateAuth()):
        return MessageContainer(
            header=u'%s' % L('Success'),
            message=u'%s' % L('Authorization complete')
        )
    else:
        return BadAuthMessage()


def ValidateAuth():
    #return (Dict['token'] or
    #    (Prefs['username'] and Prefs['password'] and CheckToken())
    #)
    #Dict.Reset()
    result = (Dict['token'] or
        (Prefs['username'] and Prefs['password'] and CheckToken())
    )
	
    if(result and Prefs['use_request_instead_of_audio_api']):
        result = (result and CheckToken_http())
    return result

###############################################################################
# Video
###############################################################################

@handler(PREFIX_V, u'%s' % L('VideoTitle'), thumb=ICON_V)
def VideoMainMenu():
    if not Dict['token']:
        return BadAuthMessage()

    oc = ObjectContainer(title2=TITLE, no_cache=True)

    Updater(PREFIX_V+'/update', oc)

    oc.add(DirectoryObject(
        key=Callback(VideoListGroups, uid=Dict['user_id']),
        title=u'%s' % L('My groups')
    ))
    oc.add(DirectoryObject(
        key=Callback(VideoListFriends, uid=Dict['user_id']),
        title=u'%s' % L('My friends')
    ))
    oc.add(DirectoryObject(
        key=Callback(VideoListSubscriptions, uid=Dict['user_id']),
        title=u'%s' % L('My subscriptions')
    ))

    oc.add(InputDirectoryObject(
        key=Callback(
            Search,
            search_type='video',
            title=u'%s' % L('Search Video')
        ),
        title=u'%s' % L('Search'), prompt=u'%s' % L('Search Video')
    ))
    return AddVideoAlbums(oc, Dict['user_id'])


@route(PREFIX_V + '/groups')
def VideoListGroups(uid, offset=0):
    return GetGroups(VideoAlbums, VideoListGroups, uid, offset);


@route(PREFIX_V + '/subscriptions')
def VideoListSubscriptions(uid, offset=0):
    return GetSubscriptions(VideoAlbums, VideoListSubscriptions, uid, offset)


@route(PREFIX_V + '/friends')
def VideoListFriends(uid, offset=0):
    return GetFriends(VideoAlbums, VideoListFriends, uid, offset)


@route(PREFIX_V + '/albums')
def VideoAlbums(uid, title, offset=0):
    oc = ObjectContainer(
        title2=u'%s' % title,
        replace_parent=(offset > 0)
    )
    return AddVideoAlbums(oc, uid, offset)


@route(PREFIX_V + '/list')
def VideoList(uid, title, album_id=None, offset=0):
    params = {
        'owner_id': uid,
        'width': 320,
        'count': Prefs['video_per_page'],
        'offset': offset
    }
    if album_id is not None:
        params['album_id'] = album_id

    res = ApiRequest('video.get', params)

    if not res or not res['count']:
        return NoContents()

    oc = ObjectContainer(
        title2=(u'%s' % title),
        content=ContainerContent.GenericVideos,
        replace_parent=(offset > 0)
    )

    for item in res['items']:
        try:
            vco = GetVideoObject(item)
            oc.add(vco)
        except Exception as e:
            try:
                Log.Warn('Can\'t add video to list: %s', e.status)
            except:
                continue

    offset = int(offset)+VK_LIMIT
    if offset < res['count']:
        oc.add(NextPageObject(
            key=Callback(
                VideoList,
                uid=uid,
                title=title,
                album_id=album_id,
                offset=offset
            ),
            title=u'%s' % L('Next page')
        ))

    return oc


@route(PREFIX_V + '/play')
def VideoPlay(uid, vid, includeBandwidths=True):

    res = ApiRequest('video.get', {
        'owner_id': uid,
        'videos': '%s_%s' % (uid, vid),
        'width': 320,
    })

    if not res or not res['count']:
        raise Ex.MediaNotAvailable

    item = res['items'][0]

    if not item:
        raise Ex.MediaNotAvailable

    return ObjectContainer(
        objects=[GetVideoObject(item)],
        content=ContainerContent.GenericVideos
    )


def AddVideoAlbums(oc, uid, offset=0):
    albums = ApiRequest('video.getAlbums', {
        'owner_id': uid,
        'extended': 1,
        'count': VK_LIMIT,
        'offset': offset
    })

    has_albums = albums and albums['count']
    offset = int(offset)

    if not offset:
        if not has_albums and not len(oc.objects):
            return VideoList(uid=uid, title=u'%s' % L('All videos'))
        else:
            oc.add(DirectoryObject(
                key=Callback(
                    VideoList, uid=uid,
                    title=u'%s' % L('All videos'),
                ),
                title=u'%s' % L('All videos'),
            ))


    if has_albums:
        for item in albums['items']:
            # display playlist title and number of videos
            title = u'%s: %s (%d)' % (L('Album'), item['title'], item['count'])
            if 'photo_320' in item:
                thumb = item['photo_320']
            else:
                thumb = R(ICON)
            
            oc.add(DirectoryObject(
                key=Callback(
                    VideoList, uid=uid,
                    title=u'%s' % item['title'],
                    #album_id=item['id']
                    album_id=item['album_id']
                ),
                title=title,
                thumb=thumb
            ))

        offset = offset+VK_LIMIT
        if offset < albums['count']:
            oc.add(NextPageObject(
                key=Callback(
                    VideoAlbums,
                    uid=uid,
                    title=oc.title2,
                    offset=offset
                ),
                title=u'%s' % L('More albums')
            ))

    return oc

def GetVideoObject(item):
    if 'external' in item['files']:
        return URLService.MetadataObjectForURL(
            item['files']['external']
        )

    return VideoClipObject(
        key=Callback(
            VideoPlay,
            uid=item['owner_id'],
            vid=item['id']
        ),
        rating_key='%s.%s' % (Plugin.Identifier, item['id']),
        title=u'%s' % item['title'],
        source_title=TITLE,
        summary=item['description'],
        thumb=item['photo_320'],
        source_icon=R(ICON),
        originally_available_at=Datetime.FromTimestamp(item['date']),
        duration=(item['duration']*1000),
        items=[
            MediaObject(
                parts=[PartObject(
                    key=item['files'][r]
                )],
                video_resolution=r.replace('mp4_', ''),
                container=Container.MP4,
                video_codec=VideoCodec.H264,
                audio_codec=AudioCodec.AAC,
                optimized_for_streaming=True
            ) for r in sorted(item['files'], reverse=True) if 'mp4_' in r
        ]
    )


###############################################################################
# Music
###############################################################################

@handler(PREFIX_M, u'%s' % L('MusicTitle'), thumb=ICON_M)
def MusicMainMenu():

    if not Dict['token']:
        return BadAuthMessage()

    oc = ObjectContainer(title2=TITLE, no_cache=True)

    Updater(PREFIX_M+'/update', oc)

    oc.add(DirectoryObject(
        key=Callback(MusicListGroups, uid=Dict['user_id']),
        title=u'%s' % L('My groups')
    ))
    oc.add(DirectoryObject(
        key=Callback(MusicListFriends, uid=Dict['user_id']),
        title=u'%s' % L('My friends')
    ))
    oc.add(DirectoryObject(
        key=Callback(MusicListSubscriptions, uid=Dict['user_id']),
        title=u'%s' % L('My subscriptions')
    ))
    
    oc.add(InputDirectoryObject(
        key=Callback(
            Search,
            search_type='audio',
            title=u'%s' % L('Search Music')
        ),
        title=u'%s' % L('Search'), prompt=u'%s' % L('Search Music')
    ))

    return AddMusicAlbums(oc, Dict['user_id'])


@route(PREFIX_M + '/groups')
def MusicListGroups(uid, offset=0):
    return GetGroups(MusicAlbums, MusicListGroups, uid, offset)


@route(PREFIX_M + '/subscriptions')
def MusicListSubscriptions(uid, offset=0):
    return GetSubscriptions(MusicAlbums, MusicListSubscriptions, uid, offset)


@route(PREFIX_M + '/friends')
def MusicListFriends(uid, offset=0):
    return GetFriends(MusicAlbums, MusicListFriends, uid, offset)


@route(PREFIX_M + '/albums')
def MusicAlbums(uid, title, offset=0):
    oc = ObjectContainer(
        title2=u'%s' % title,
        replace_parent=(offset > 0)
    )
    return AddMusicAlbums(oc, uid, offset)


@route(PREFIX_M + '/list')
def MusicList(uid, title, album_id=None, offset=0):

    params = {
        'owner_id': uid,
        'count': Prefs['audio_per_page'],
        'offset': offset
    }
    if album_id is not None:
        params['album_id'] = album_id

    if(Prefs['use_request_instead_of_audio_api']):
        res = GetAudioHttp(params)
    else:
        res = ApiRequest('audio.get', params)

    if not res or not res['count']:
        return NoContents()

    oc = ObjectContainer(
        title2=(u'%s' % title),
        content=ContainerContent.Tracks,
        replace_parent=(offset > 0)
    )

    for item in res['items']:
        oc.add(GetTrackObject(item))

    offset = int(offset)+VK_LIMIT
    if offset < res['count']:
        oc.add(NextPageObject(
            key=Callback(
                MusicList,
                uid=uid,
                title=title,
                album_id=album_id,
                offset=offset
            ),
            title=u'%s' % L('Next page')
        ))

    return oc


@route(PREFIX_M + '/play')
def MusicPlay(info, includeBandwidths = True):

    item = JSON.ObjectFromString(info)

    if not item:
        raise Ex.MediaNotAvailable

    return ObjectContainer(
        objects=[GetTrackObject(item)],
        content=ContainerContent.Tracks,
        no_cache=True
    )

    return oc


def AddMusicAlbums(oc, uid, offset=0):

    if(uid==Dict['user_id'] and Prefs['use_request_instead_of_audio_api']):
        albums = GetAlbumsHttp()
    else:
        albums = ApiRequest('audio.getAlbums', {
            'owner_id': uid,
            'count': VK_LIMIT,
            'offset': offset
        })

    has_albums = albums and albums['count']
    offset = int(offset)

    if not offset:
        if not has_albums and not len(oc.objects):
            return MusicList(uid=uid, title=u'%s' % L('All tracks'))
        else:
            oc.add(DirectoryObject(
                key=Callback(
                    MusicList, uid=uid,
                    title=u'%s' % L('All tracks'),
                ),
                title=u'%s' % L('All tracks'),
            ))

    if has_albums:
        for item in albums['items']:
            album_id = item['id']
            # display playlist title and number of videos
            title = u'%s: %s' % (L('Album'), item['title'])
            oc.add(DirectoryObject(
                key=Callback(
                    MusicList, uid=uid,
                    title=u'%s' % item['title'],
                    album_id=album_id
                ),
                title=title,
            ))

        offset = offset+VK_LIMIT
        if offset < albums['count']:
            oc.add(NextPageObject(
                key=Callback(
                    MusicAlbums,
                    uid=uid,
                    title=oc.title2,
                    offset=offset
                ),
                title=u'%s' % L('More albums')
            ))

    return oc


def GetTrackObject(item):

    return TrackObject(
        key=Callback(MusicPlay, info=JSON.StringFromObject(item)),
        # rating_key='%s.%s' % (Plugin.Identifier, item['id']),
        # Rating key must be integer because PHT and PlexConnect
        # does not support playing queue with string rating key
        rating_key=item['id'],
        title=u'%s' % item['title'],
        artist=u'%s' % item['artist'],
        duration=int(item['duration'])*1000,
        items=[
            MediaObject(
                parts=[PartObject(key=Callback(GetUrlHttpForId, url=item['url'], album_id=item['album_id'], id=item['id']))],
                container=Container.MP3,
                audio_codec=AudioCodec.MP3,
                audio_channels=2,
                video_codec='',  # Crutch for disable generate parts,
                optimized_for_streaming=True,
            )
        ]
    )


###############################################################################
# Photos
###############################################################################

@handler(PREFIX_P, u'%s' % L('PhotosTitle'), thumb=ICON_P)
def PhotoMainMenu():
    if not Dict['token']:
        return BadAuthMessage()

    oc = ObjectContainer(title2=TITLE, no_cache=True)

    Updater(PREFIX_P+'/update', oc)

    oc.add(DirectoryObject(
        key=Callback(PhotoListGroups, uid=Dict['user_id']),
        title=u'%s' % L('My groups')
    ))
    oc.add(DirectoryObject(
        key=Callback(PhotoListFriends, uid=Dict['user_id']),
        title=u'%s' % L('My friends')
    ))
    oc.add(DirectoryObject(
        key=Callback(PhotoListSubscriptions, uid=Dict['user_id']),
        title=u'%s' % L('My subscriptions')
    ))

    return AddPhotoAlbums(oc, Dict['user_id'])


@route(PREFIX_P + '/groups')
def PhotoListGroups(uid, offset=0):
    return GetGroups(PhotoAlbums, PhotoListGroups, uid, offset)


@route(PREFIX_P + '/subscriptions')
def PhotoListSubscriptions(uid, offset=0):
    return GetSubscriptions(PhotoAlbums, PhotoListSubscriptions, uid, offset)


@route(PREFIX_P + '/friends')
def PhotoListFriends(uid, offset=0):
    return GetFriends(PhotoAlbums, PhotoListFriends, uid, offset)


@route(PREFIX_P + '/albums')
def PhotoAlbums(uid, title, offset=0):
    oc = ObjectContainer(title2=u'%s' % title, replace_parent=(offset > 0))
    return AddPhotoAlbums(oc, uid, offset)


@route(PREFIX_P + '/list')
def PhotoList(uid, title, album_id, offset=0):
    res = ApiRequest('photos.get', {
        'owner_id': uid,
        'album_id': album_id,
        'extended': 0,
        'photo_sizes': 1,
        'rev': 1,
        'count': Prefs['photos_per_page'],
        'offset': offset
    })

    if not res or not res['count']:
        return NoContents()

    oc = ObjectContainer(
        title2=(u'%s' % title),
        content='photo',
        replace_parent=(offset > 0)
    )

    for item in res['items']:
        oc.add(GetPhotoObject(item))

    offset = int(offset)+VK_LIMIT
    if offset < res['count']:
        oc.add(NextPageObject(
            key=Callback(
                PhotoList,
                uid=uid,
                title=title,
                album_id=album_id,
                offset=offset
            ),
            title=u'%s' % L('Next page')
        ))

    return oc


def AddPhotoAlbums(oc, uid, offset=0):

    albums = ApiRequest('photos.getAlbums', {
        'owner_id': uid,
        'need_covers': 1,
        'photo_sizes': 1,
        'need_system': 1,
        'count': VK_LIMIT,
        'offset': offset
    })

    has_albums = albums and albums['count']
    offset = int(offset)

    if has_albums:
        for item in albums['items']:
            thumb = ''
            for size in item['sizes']:
                if size['type'] == 'p':
                    thumb = size['src']
                    break

            oc.add(DirectoryObject(
                key=Callback(
                    PhotoList, uid=uid,
                    title=u'%s' % item['title'],
                    album_id=item['id']
                ),
                summary=item['description'] if 'description' in item else '',
                title=u'%s (%s)' % (item['title'], item['size']),
                thumb=thumb,
            ))

        offset = offset+VK_LIMIT
        if offset < albums['count']:
            oc.add(NextPageObject(
                key=Callback(
                    PhotoAlbums,
                    uid=uid,
                    title=oc.title2,
                    offset=offset
                ),
                title=u'%s' % L('More albums')
            ))

    if not len(oc.objects):
        return NoContents()

    return oc


def GetPhotoObject(item):

    sizes = {}
    for size in item['sizes']:
        sizes[size['type']] = size['src']

    url = ''
    for size in ['z', 'y', 'x']:
        if size in sizes:
            url = sizes[size]
            break

    return PhotoObject(
        key=url,
        rating_key='%s.%s' % (Plugin.Identifier, item['id']),
        summary=u'%s' % item['text'],
        thumb=sizes['p'] if 'p' in sizes else ''
    )


###############################################################################
# Common
###############################################################################

def Search(query, title=u'%s' % L('Search'), search_type='video', offset=0):

    is_video = search_type == 'video'

    params = {
        'sort': 2,
        'offset': offset,
        'count': Prefs[search_type + '_per_page'],
        'q': query
    }

    if is_video:
        if Prefs['search_hd']:
            params['hd'] = 1
        if Prefs['search_adult']:
            params['adult'] = 1

    res = ApiRequest(search_type+'.search', params)

    if not res or not res['count']:
        return NoContents()

    oc = ObjectContainer(
        title2=(u'%s' % title),
        replace_parent=(offset > 0),
    )

    if is_video:
        method = GetVideoObject
        oc.content = ContainerContent.GenericVideos
    else:
        method = GetTrackObject
        oc.content = ContainerContent.Tracks

    for item in res['items']:
        oc.add(method(item))

    offset = int(offset)+VK_LIMIT
    if offset < res['count']:
        oc.add(NextPageObject(
            key=Callback(
                Search,
                query=query,
                title=title,
                search_type=search_type,
                offset=offset
            ),
            title=u'%s' % L('Next page')
        ))

    return oc


def BadAuthMessage():
    return MessageContainer(
        header=u'%s' % L('Error'),
        message=u'%s' % L('NotAuth')
    )


def NoContents():
    return ObjectContainer(
        header=u'%s' % L('Error'),
        message=u'%s' % L('No entries found')
    )


def GetGroups(callback_action, callback_page, uid, offset):
    '''Get groups container with custom callback'''
    oc = ObjectContainer(
        title2=u'%s' % L('My groups'),
        replace_parent=(offset > 0)
    )

    return AddSocialObjects(
        oc=oc,
        method='groups.get',
        callback_action=callback_action,
        callback_page=callback_page,
        uid=uid,
        offset=offset
    )


def GetSubscriptions(callback_action, callback_page, uid, offset):
    '''Get Subscriptions container with custom callback'''
    oc = ObjectContainer(
        title2=u'%s' % L('My subscriptions'),
        replace_parent=(offset > 0)
    )

    return AddSocialObjects(
        oc=oc,
        method='users.getSubscriptions',
        callback_action=callback_action,
        callback_page=callback_page,
        uid=uid,
        offset=offset
    )


def GetFriends(callback_action, callback_page, uid, offset):
    '''Get friends container with custom callback'''
    oc = ObjectContainer(
        title2=u'%s' % L('My friends'),
        replace_parent=(offset > 0)
    )
    return AddSocialObjects(
        oc=oc,
        method='friends.get',
        callback_action=callback_action,
        callback_page=callback_page,
        uid=uid,
        offset=offset
    )


def AddSocialObjects(oc, method, callback_action, callback_page, uid, offset):
    items = ApiRequest(method, {
        'user_id': uid,
        'extended': 1,
        'fields': 'photo_200',
        'count': VK_LIMIT,
        'offset': offset,
        'order': 'hints',

    })
    if items and items['count']:
        for item in items['items']:
            oc.add(SocialDirectoryObject(callback_action, item))

        offset = int(offset)+VK_LIMIT
        if offset < items['count']:
            oc.add(NextPageObject(
                key=Callback(
                    callback_page,
                    uid=uid,
                    offset=offset
                ),
                title=u'%s' % L('Next page')
            ))

    return oc


def SocialDirectoryObject(callback_action, item):

    if 'name' in item: # Group or page
        title = u'%s' % item['name']
        uid = (item['id']*-1)
    else:
        title = u'%s %s' % (item['first_name'], item['last_name'])
        uid = item['id']

    return DirectoryObject(
        key=Callback(
            callback_action,
            uid=uid,
            title=title,
        ),
        title=title,
        thumb=item['photo_200'] if 'photo_200' in item else R(ICON)
    )


def ApiRequest(method, params):
    params['access_token'] = Dict['token']
    params['v'] = VK_VERSION
    res = JSON.ObjectFromURL(
        'https://api.vk.com/method/%s?%s' % (method, urlencode(params)),
    )

    if res and ('response' in res):
        return res['response']

    return False


def CheckToken():
    url = 'https://oauth.vk.com/token?' + urlencode({
        'grant_type': 'password',
        'client_id': VK_APP_ID,
        'client_secret': VK_APP_SECRET,
        'username': Prefs['username'],
        'password': Prefs['password'],
        'scope': VK_APP_SCOPE,
        'v': VK_VERSION
    })
    res = JSON.ObjectFromURL(url)

    if res and ('access_token' in res):
        Dict['token'] = res['access_token']
        Dict['user_id'] = res['user_id']
        Dict.Save()
        return True

    return False

##############################################
# VK http api and pseudo-api
##############################################
class NoRedirection(urllib2.HTTPErrorProcessor):
    def http_response(self, request, response):
        return response
    https_response = http_response

def vk_t(url):
    vk_str="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMN0PQRSTUVWXYZO123456789+/="
    result = ""
    if(url.find('audio_api_unavailable')>0):
        urls = url.split("?extra=")[1].split('#')
        e = vk_o(urls[1],vk_str)
        i = vk_o(urls[0],vk_str)
        if(len(e)>0 and len(i)>0):
            e = e.split(chr(9))
            index = 1
            while index<=len(e):
                r = e[len(e)-index].split(chr(11))
                index = index+1
                if(r[0]=='v'):
                    i = i[::-1]
                elif(r[0]=='r'):
                    double_vk_str = vk_str+vk_str
                    tt = list(i)
                    index2 = 1
                    while index2<=len(tt):
                        symindex = tt[len(tt)-index2]
                        ee = double_vk_str.find(symindex)
                        if(ee > -1):
                            tt[len(tt)-index2]=double_vk_str[ee-int(r[1])]
                        index2 = index2+1
                    i = ("").join(tt)
                elif(r[0]=='x'):
                    ii = ord(r[1][0])
                    index2 = 0
                    tt = list(i)
                    while index2<len(tt):
                        tt[index2] = chr(ord(tt[index2]) ^ ii)
                        index2 = index2+1
                    i = ("").join(tt)
            result = i
    return result

def vk_o(url, vk_str):
    result = ''
    s = 0
    while s<len(url):
        symindex = vk_str.find(url[s])
        if symindex > -1:
            if ((s % 4)>0):
                i = 64 * i + symindex
                result = result + chr(255 & i >> (-2 * (s+1) & 6 ))
            else:
                i = symindex
        s=s+1
    return result

def GetCookies(type = 0):
    cookie = "remixdt=" + Dict['http_request']['remixdt'] + "; remixlang=" + Dict['http_request']['remixlang'] + "; remixflash=" + Dict['http_request']['remixflash'] + "; remixscreen_depth=" + Dict['http_request']['remixscreen_depth']
    if(type<0):
        cookie = cookie + "; remixlhk=" + Dict['http_request']['remixlhk']
    if(type<-1):
        cookie = cookie + "; " + Dict['http_request']['remixqkey'] + "=" + Dict['http_request']['remixqvalue']
    if(type==0):
        cookie = cookie + "; remixsslsid=" + Dict['http_request']['remixsslsid'] + "; remixsid=" + Dict['http_request']['remixsid']
    return cookie

def DecodeStream(response):
    if response.info().get('Content-Encoding') == 'gzip':
        buf = StringIO(response.read())
        f = gzip.GzipFile(fileobj=buf)
        data = f.read()
    else:
        data - respose.read()
    return data

def CheckToken_http():

    Dict['http_request'] = {
        'iph': '',
        'lgh': '',
        'remixdt': '7200',
        'remixflash': '24.0.0',
        'remixlang': '0',
        'remixscreen_depth': '24',
        'remixlhk': '',
        'remixsid': '',
        'remixsslsid': '1',
		'remixmdevice': '1366/768/1/!!!!!!!',
		'remixmhideads': '1'
    };

    data = urllib2.urlopen('http://vk.com')
    d = data.read()
    cookie = data.info().getheader('Set-Cookie')
    cookie = cookie[cookie.find('remixlang=')+len('remixlang='):]
    Dict['http_request']['remixlang'] = cookie[:cookie.find(';')]
    cookie = cookie[cookie.find('remixlhk=')+len('remixlhk='):]
    Dict['http_request']['remixlhk'] = cookie[:cookie.find(';')]
    d = d[d.find('ip_h=')+len('ip_h='):]
    Dict['http_request']['iph'] = d[:d.find('&')]
    d = d[d.find('lg_h=')+len('lg_h='):]
    Dict['http_request']['lgh'] = d[:d.find('&')]
    
    #Let's try to login with this params
    url = 'https://login.vk.com/?act=login'
    req = urllib2.Request(url)
    request = urlencode({
        'act': 'login',
        'role': 'pda',
        'expire': '',
        'captcha_sid': '',
        'captcha_key': '',
        '_origin': 'https://vk.com',
        'email': Prefs['username'],
        'pass': Prefs['password'],
        'ip_h': Dict['http_request']['iph'],
        'lg_h': Dict['http_request']['lgh']})
    
    req.add_header('Content-Type','application/x-www-form-urlencoded')
    req.add_header('Origin','https://vk.com')
    req.add_header('Referer','https://vk.com/login?act=mobile')
    req.add_header("Cookie", GetCookies(-1))
    req.add_header('Accept-Encoding','gzip, deflate, br')
    req.add_header('Cache-Control','max-age=0')
    req.add_header('Accept-Language', 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4')
    req.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')
    opener = urllib2.build_opener(NoRedirection)
    data = opener.open(req, request)
    
    cookie = data.info().getallmatchingheaders('Set-Cookie')
    for c in cookie:
        templatefound = c.find('Set-Cookie: remixq_')
        if templatefound <> -1:
            c = c[len('Set-Cookie: '):]
            Dict['http_request']['remixqkey'] = c[:c.find('=')]
            c = c[len(Dict['http_request']['remixqkey'])+1:]
            Dict['http_request']['remixqvalue'] = c[:c.find(';')]

    loginurl = data.info().getheader('Location')
    
    req = urllib2.Request(loginurl)
    req.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')
    req.add_header('Accept-Language', 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4')
    req.add_header('Accept-Encoding','gzip, deflate, sdch, br')
    req.add_header('Cache-Control','max-age=0')
    req.add_header('Referer','https://vk.com/login?act=mobile')
    req.add_header("Cookie", GetCookies(-2))
    opener = urllib2.build_opener(NoRedirection)
    data = opener.open(req)
    
    cookie = data.info().getallmatchingheaders('Set-Cookie')
    for c in cookie:
        templatefound = c.find('Set-Cookie: remixsid')
        if templatefound <> -1:
            c = c[len('Set-Cookie: remixsid='):]
            Dict['http_request']['remixsid'] = c[:c.find(';')]
        templatefound = c.find('Set-Cookie: remixlang')
        if templatefound <> -1:
            c = c[len('Set-Cookie: remixlang='):]
            Dict['http_request']['remixlang'] = c[:c.find(';')]
    Dict.Save()
    return True

def GetAlbumsHttp():
    
    #Loading audio page for retrieving audio albums
    url = "https://vk.com/audios" + str(Dict['user_id'])
    req = urllib2.Request(url)
    req.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')
    req.add_header('Accept-Language', 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4')
    req.add_header('Accept-Encoding','gzip, deflate, sdch, br')
    req.add_header('Cache-Control','max-age=0')
    req.add_header("Cookie", GetCookies())
    req.add_header('User-Agent','Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36')
    response = urllib2.urlopen(req)
    if response.info().get('Content-Encoding') == 'gzip':
         buf = StringIO(response.read())
         f = gzip.GzipFile(fileobj=buf)
         data = f.read()
    albums = {'count':0,'items':[]}
    blockstart = data.find('?album_id=')
    h = HTMLParser.HTMLParser()
    while blockstart>0:
        data = data[blockstart+len('?album_id='):]
        key = data[:data.find('"')]
        data = data[data.find('"')+1:]
        bvstart = data.find('class="audio_album_title"')
        data = data[bvstart+len('class="audio_album_title"'):]
        value = h.unescape(data[data.find('>')+1:data.find('</div>')])
        albums['items'].append({'id': key.decode('cp1251'), 'title': value.decode('cp1251')})
        albums['count'] = albums['count']+1
        blockstart = data.find('?album_id=')
    return albums

def GetAudioHttp(params):    
    #Loading audio
    h = HTMLParser.HTMLParser()
    url = 'https://vk.com/al_audio.php'
    req = urllib2.Request(url)
    req.add_header('Accept', '*/*')
    req.add_header('Accept-Language', 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4')
    req.add_header('Accept-Encoding','gzip, deflate, br')
    req.add_header('Cache-Control','max-age=0')
    req.add_header('Content-Type','application/x-www-form-urlencoded')
    req.add_header('Origin','https://vk.com')
    req.add_header('Referer','https://vk.com/audio')
    req.add_header('X-Requested-With','XMLHttpRequest')
    req.add_header('Host','vk.com')
    req.add_header("Cookie", GetCookies())
    album_id = params.get('album_id', -2)
    request = urlencode({
        'act': 'load_silent',
        'al': '1',
        'band': 'false',
        'album_id': str(album_id),
        'owner_id': params['owner_id']
    })

    response = urllib2.urlopen(req, request)
    if response.info().get('Content-Encoding') == 'gzip':
         buf = StringIO(response.read())
         f = gzip.GzipFile(fileobj=buf)
         data = f.read()
    data = data.decode('cp1251')
    data = data[data.find('<!json>')+len('<!json>'):]
    data = data[:data.find('<!>')]
    item = JSON.ObjectFromString(data)

    items = {'count': 0, 'items': []}
    for aud in item['list']:
        items['count'] = items['count']+1
        items['items'].append({'id': aud[0], 'title': h.unescape(aud[3]), 'artist': h.unescape(aud[4]), 'duration': aud[5], 'url': 'https://vk.com/mp3/audio_api_unavailable.mp3', 'owner_id': params['owner_id'],'album_id': aud[1]})

    return items

#@indirect
@route(PREFIX_M + '/GetUrlHttpForId')
def GetUrlHttpForId(url, album_id, id):
    fullid = album_id+"_"+id
    newurl = vk_t(GetUrlHttpFromId(fullid))
    return Redirect(newurl)

def GetUrlHttpFromId(fullid):
    #Reloading audio
    url = 'https://vk.com/al_audio.php'
    req = urllib2.Request(url)
    req.add_header('Accept', '*/*')
    req.add_header('Accept-Language', 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4')
    req.add_header('Accept-Encoding','gzip, deflate, br')
    req.add_header('Content-Type','application/x-www-form-urlencoded')
    req.add_header('Origin','https://vk.com')
    req.add_header('Referer','https://vk.com/audio')
    req.add_header('X-Requested-With','XMLHttpRequest')
    req.add_header('Host','vk.com')
    
    req.add_header("Cookie", GetCookies())
    request = urlencode({
        'act': 'reload_audio',
        'al': '1',
        'ids': fullid})
    response = urllib2.urlopen(req, request)
    if response.info().get('Content-Encoding') == 'gzip':
         buf = StringIO(response.read())
         f = gzip.GzipFile(fileobj=buf)
         data = f.read()
    data = data[data.find('<!json>')+len('<!json>'):]
    data = data[:data.find('<!>')]
    itemr = JSON.ObjectFromString(unicode(data.decode('cp1251')))
    i = itemr[0]
    return i[2]