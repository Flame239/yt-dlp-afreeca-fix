import functools
import re

from .common import InfoExtractor
from ..utils import (
    ExtractorError,
    OnDemandPagedList,
    date_from_str,
    determine_ext,
    int_or_none,
    qualities,
    traverse_obj,
    unified_strdate,
    unified_timestamp,
    update_url_query,
    url_or_none,
    urlencode_postdata,
)


class AfreecaTVIE(InfoExtractor):
    IE_NAME = 'afreecatv'
    IE_DESC = 'afreecatv.com'
    _VALID_URL = r'''(?x)
                    https?://
                        (?:
                            (?:(?:live|afbbs|www)\.)?afreeca(?:tv)?\.com(?::\d+)?
                            (?:
                                /app/(?:index|read_ucc_bbs)\.cgi|
                                /player/[Pp]layer\.(?:swf|html)
                            )\?.*?\bnTitleNo=|
                            vod\.afreecatv\.com/(PLAYER/STATION|player)/
                        )
                        (?P<id>\d+)
                    '''
    _NETRC_MACHINE = 'afreecatv'
    _TESTS = [{
        'url': 'http://live.afreecatv.com:8079/app/index.cgi?szType=read_ucc_bbs&szBjId=dailyapril&nStationNo=16711924&nBbsNo=18605867&nTitleNo=36164052&szSkin=',
        'md5': 'f72c89fe7ecc14c1b5ce506c4996046e',
        'info_dict': {
            'id': '36164052',
            'ext': 'mp4',
            'title': '데일리 에이프릴 요정들의 시상식!',
            'thumbnail': 're:^https?://(?:video|st)img.afreecatv.com/.*$',
            'uploader': 'dailyapril',
            'uploader_id': 'dailyapril',
            'upload_date': '20160503',
        },
        'skip': 'Video is gone',
    }, {
        'url': 'http://afbbs.afreecatv.com:8080/app/read_ucc_bbs.cgi?nStationNo=16711924&nTitleNo=36153164&szBjId=dailyapril&nBbsNo=18605867',
        'info_dict': {
            'id': '36153164',
            'title': "BJ유트루와 함께하는 '팅커벨 메이크업!'",
            'thumbnail': 're:^https?://(?:video|st)img.afreecatv.com/.*$',
            'uploader': 'dailyapril',
            'uploader_id': 'dailyapril',
        },
        'playlist_count': 2,
        'playlist': [{
            'md5': 'd8b7c174568da61d774ef0203159bf97',
            'info_dict': {
                'id': '36153164_1',
                'ext': 'mp4',
                'title': "BJ유트루와 함께하는 '팅커벨 메이크업!'",
                'upload_date': '20160502',
            },
        }, {
            'md5': '58f2ce7f6044e34439ab2d50612ab02b',
            'info_dict': {
                'id': '36153164_2',
                'ext': 'mp4',
                'title': "BJ유트루와 함께하는 '팅커벨 메이크업!'",
                'upload_date': '20160502',
            },
        }],
        'skip': 'Video is gone',
    }, {
        # non standard key
        'url': 'http://vod.afreecatv.com/PLAYER/STATION/20515605',
        'info_dict': {
            'id': '20170411_BE689A0E_190960999_1_2_h',
            'ext': 'mp4',
            'title': '혼자사는여자집',
            'thumbnail': 're:^https?://(?:video|st)img.afreecatv.com/.*$',
            'uploader': '♥이슬이',
            'uploader_id': 'dasl8121',
            'upload_date': '20170411',
            'duration': 213,
        },
        'params': {
            'skip_download': True,
        },
    }, {
        # adult content
        'url': 'https://vod.afreecatv.com/player/97267690',
        'info_dict': {
            'id': '20180327_27901457_202289533_1',
            'ext': 'mp4',
            'title': '[생]빨개요♥ (part 1)',
            'thumbnail': 're:^https?://(?:video|st)img.afreecatv.com/.*$',
            'uploader': '[SA]서아',
            'uploader_id': 'bjdyrksu',
            'upload_date': '20180327',
            'duration': 3601,
        },
        'params': {
            'skip_download': True,
        },
        'skip': 'The VOD does not exist',
    }, {
        'url': 'http://www.afreecatv.com/player/Player.swf?szType=szBjId=djleegoon&nStationNo=11273158&nBbsNo=13161095&nTitleNo=36327652',
        'only_matching': True,
    }, {
        'url': 'https://vod.afreecatv.com/player/96753363',
        'info_dict': {
            'id': '20230108_9FF5BEE1_244432674_1',
            'ext': 'mp4',
            'uploader_id': 'rlantnghks',
            'uploader': '페이즈으',
            'duration': 10840,
            'thumbnail': 'http://videoimg.afreecatv.com/php/SnapshotLoad.php?rowKey=20230108_9FF5BEE1_244432674_1_r',
            'upload_date': '20230108',
            'title': '젠지 페이즈',
        },
        'params': {
            'skip_download': True,
        },
    }]

    @staticmethod
    def parse_video_key(key):
        video_key = {}
        m = re.match(r'^(?P<upload_date>\d{8})_\w+_(?P<part>\d+)$', key)
        if m:
            video_key['upload_date'] = m.group('upload_date')
            video_key['part'] = int(m.group('part'))
        return video_key

    def _perform_login(self, username, password):
        login_form = {
            'szWork': 'login',
            'szType': 'json',
            'szUid': username,
            'szPassword': password,
            'isSaveId': 'false',
            'szScriptVar': 'oLoginRet',
            'szAction': '',
        }

        response = self._download_json(
            'https://login.afreecatv.com/app/LoginAction.php', None,
            'Logging in', data=urlencode_postdata(login_form))

        _ERRORS = {
            -4: 'Your account has been suspended due to a violation of our terms and policies.',
            -5: 'https://member.afreecatv.com/app/user_delete_progress.php',
            -6: 'https://login.afreecatv.com/membership/changeMember.php',
            -8: "Hello! AfreecaTV here.\nThe username you have entered belongs to \n an account that requires a legal guardian's consent. \nIf you wish to use our services without restriction, \nplease make sure to go through the necessary verification process.",
            -9: 'https://member.afreecatv.com/app/pop_login_block.php',
            -11: 'https://login.afreecatv.com/afreeca/second_login.php',
            -12: 'https://member.afreecatv.com/app/user_security.php',
            0: 'The username does not exist or you have entered the wrong password.',
            -1: 'The username does not exist or you have entered the wrong password.',
            -3: 'You have entered your username/password incorrectly.',
            -7: 'You cannot use your Global AfreecaTV account to access Korean AfreecaTV.',
            -10: 'Sorry for the inconvenience. \nYour account has been blocked due to an unauthorized access. \nPlease contact our Help Center for assistance.',
            -32008: 'You have failed to log in. Please contact our Help Center.',
        }

        result = int_or_none(response.get('RESULT'))
        if result != 1:
            error = _ERRORS.get(result, 'You have failed to log in.')
            raise ExtractorError(
                'Unable to login: %s said: %s' % (self.IE_NAME, error),
                expected=True)

    def _real_extract(self, url):
        video_id = self._match_id(url)

        partial_view = False
        adult_view = False
        for _ in range(2):
            data = self._download_json(
                'https://api.m.afreecatv.com/station/video/a/view',
                video_id, headers={'Referer': url}, data=urlencode_postdata({
                    'nTitleNo': video_id,
                    'nApiLevel': 10,
                }))['data']
            if traverse_obj(data, ('code', {int})) == -6221:
                raise ExtractorError('The VOD does not exist', expected=True)
            query = {
                'nTitleNo': video_id,
                'nStationNo': data['station_no'],
                'nBbsNo': data['bbs_no'],
            }
            if partial_view:
                query['partialView'] = 'SKIP_ADULT'
            if adult_view:
                query['adultView'] = 'ADULT_VIEW'

            flag = data['flag']
            if flag and flag == 'SUCCEED':
                break
            if flag == 'PARTIAL_ADULT':
                self.report_warning(
                    'In accordance with local laws and regulations, underage users are restricted from watching adult content. '
                    'Only content suitable for all ages will be downloaded. '
                    'Provide account credentials if you wish to download restricted content.')
                partial_view = True
                continue
            elif flag == 'ADULT':
                if not adult_view:
                    adult_view = True
                    continue
                error = 'Only users older than 19 are able to watch this video. Provide account credentials to download this content.'
            else:
                error = flag
            raise ExtractorError(
                '%s said: %s' % (self.IE_NAME, error), expected=True)
        else:
            raise ExtractorError('Unable to download video info')

        video_element = data['files'][-1]
        if video_element is None:
            raise ExtractorError(
                'Video %s does not exist' % video_id, expected=True)

        video_url = str(video_element).strip()

        title = data['title']

        uploader = data['writer_nick']
        uploader_id = data['bj_id']
        duration = data['total_file_duration']
        thumbnail = data['thumb']

        common_entry = {
            'uploader': uploader,
            'uploader_id': uploader_id,
            'thumbnail': thumbnail,
        }

        info = common_entry.copy()
        info.update({
            'id': video_id,
            'title': title,
            'duration': duration,
        })

        if video_url:
            entries = []
            file_elements = data['files']
            one = len(file_elements) == 1
            for file_num, file_element in enumerate(file_elements, start=1):
                file_url = url_or_none(file_element['file'])
                if not file_url:
                    continue
                key = file_element['file_info_key']
                upload_date = unified_strdate(self._search_regex(
                    r'^(\d{8})_', key, 'upload date', default=None))
                if upload_date is not None:
                    # sometimes the upload date isn't included in the file name
                    # instead, another random ID is, which may parse as a valid
                    # date but be wildly out of a reasonable range
                    parsed_date = date_from_str(upload_date)
                    if parsed_date.year < 2000 or parsed_date.year >= 2100:
                        upload_date = None
                file_duration = int_or_none(file_element['duration'])
                format_id = key if key else '%s_%s' % (video_id, file_num)
                if determine_ext(file_url) == 'm3u8':
                    formats = self._extract_m3u8_formats(
                        file_url, video_id, 'mp4', entry_protocol='m3u8_native',
                        m3u8_id='hls',
                        note='Downloading part %d m3u8 information' % file_num)
                else:
                    formats = [{
                        'url': file_url,
                        'format_id': 'http',
                    }]
                if not formats and not self.get_param('ignore_no_formats'):
                    continue
                file_info = common_entry.copy()
                file_info.update({
                    'id': format_id,
                    'title': title if one else '%s (part %d)' % (title, file_num),
                    'upload_date': upload_date,
                    'duration': file_duration,
                    'formats': formats,
                })
                entries.append(file_info)
            entries_info = info.copy()
            entries_info.update({
                '_type': 'multi_video',
                'entries': entries,
            })
            return entries_info

        info = {
            'id': video_id,
            'title': title,
            'uploader': uploader,
            'uploader_id': uploader_id,
            'duration': duration,
            'thumbnail': thumbnail,
        }

        if determine_ext(video_url) == 'm3u8':
            info['formats'] = self._extract_m3u8_formats(
                video_url, video_id, 'mp4', entry_protocol='m3u8_native',
                m3u8_id='hls')
        else:
            app, playpath = video_url.split('mp4:')
            info.update({
                'url': app,
                'ext': 'flv',
                'play_path': 'mp4:' + playpath,
                'rtmp_live': True,  # downloading won't end without this
            })

        return info


class AfreecaTVLiveIE(AfreecaTVIE):  # XXX: Do not subclass from concrete IE

    IE_NAME = 'afreecatv:live'
    _VALID_URL = r'https?://play\.afreeca(?:tv)?\.com/(?P<id>[^/]+)(?:/(?P<bno>\d+))?'
    _TESTS = [{
        'url': 'https://play.afreecatv.com/pyh3646/237852185',
        'info_dict': {
            'id': '237852185',
            'ext': 'mp4',
            'title': '【 우루과이 오늘은 무슨일이? 】',
            'uploader': '박진우[JINU]',
            'uploader_id': 'pyh3646',
            'timestamp': 1640661495,
            'is_live': True,
        },
        'skip': 'Livestream has ended',
    }, {
        'url': 'http://play.afreeca.com/pyh3646/237852185',
        'only_matching': True,
    }, {
        'url': 'http://play.afreeca.com/pyh3646',
        'only_matching': True,
    }]

    _LIVE_API_URL = 'https://live.afreecatv.com/afreeca/player_live_api.php'

    _QUALITIES = ('sd', 'hd', 'hd2k', 'original')

    def _real_extract(self, url):
        broadcaster_id, broadcast_no = self._match_valid_url(url).group('id', 'bno')
        password = self.get_param('videopassword')

        info = self._download_json(self._LIVE_API_URL, broadcaster_id, fatal=False,
                                   data=urlencode_postdata({'bid': broadcaster_id})) or {}
        channel_info = info.get('CHANNEL') or {}
        broadcaster_id = channel_info.get('BJID') or broadcaster_id
        broadcast_no = channel_info.get('BNO') or broadcast_no
        password_protected = channel_info.get('BPWD')
        if not broadcast_no:
            raise ExtractorError(f'Unable to extract broadcast number ({broadcaster_id} may not be live)', expected=True)
        if password_protected == 'Y' and password is None:
            raise ExtractorError(
                'This livestream is protected by a password, use the --video-password option',
                expected=True)

        formats = []
        quality_key = qualities(self._QUALITIES)
        for quality_str in self._QUALITIES:
            params = {
                'bno': broadcast_no,
                'stream_type': 'common',
                'type': 'aid',
                'quality': quality_str,
            }
            if password is not None:
                params['pwd'] = password
            aid_response = self._download_json(
                self._LIVE_API_URL, broadcast_no, fatal=False,
                data=urlencode_postdata(params),
                note=f'Downloading access token for {quality_str} stream',
                errnote=f'Unable to download access token for {quality_str} stream')
            aid = traverse_obj(aid_response, ('CHANNEL', 'AID'))
            if not aid:
                continue

            stream_base_url = channel_info.get('RMD') or 'https://livestream-manager.afreecatv.com'
            stream_info = self._download_json(
                f'{stream_base_url}/broad_stream_assign.html', broadcast_no, fatal=False,
                query={
                    'return_type': channel_info.get('CDN', 'gcp_cdn'),
                    'broad_key': f'{broadcast_no}-common-{quality_str}-hls',
                },
                note=f'Downloading metadata for {quality_str} stream',
                errnote=f'Unable to download metadata for {quality_str} stream') or {}

            if stream_info.get('view_url'):
                formats.append({
                    'format_id': quality_str,
                    'url': update_url_query(stream_info['view_url'], {'aid': aid}),
                    'ext': 'mp4',
                    'protocol': 'm3u8',
                    'quality': quality_key(quality_str),
                })

        station_info = self._download_json(
            'https://st.afreecatv.com/api/get_station_status.php', broadcast_no,
            query={'szBjId': broadcaster_id}, fatal=False,
            note='Downloading channel metadata', errnote='Unable to download channel metadata') or {}

        return {
            'id': broadcast_no,
            'title': channel_info.get('TITLE') or station_info.get('station_title'),
            'uploader': channel_info.get('BJNICK') or station_info.get('station_name'),
            'uploader_id': broadcaster_id,
            'timestamp': unified_timestamp(station_info.get('broad_start')),
            'formats': formats,
            'is_live': True,
        }


class AfreecaTVUserIE(InfoExtractor):
    IE_NAME = 'afreecatv:user'
    _VALID_URL = r'https?://bj\.afreeca(?:tv)?\.com/(?P<id>[^/]+)/vods/?(?P<slug_type>[^/]+)?'
    _TESTS = [{
        'url': 'https://bj.afreecatv.com/ryuryu24/vods/review',
        'info_dict': {
            '_type': 'playlist',
            'id': 'ryuryu24',
            'title': 'ryuryu24 - review',
        },
        'playlist_count': 218,
    }, {
        'url': 'https://bj.afreecatv.com/parang1995/vods/highlight',
        'info_dict': {
            '_type': 'playlist',
            'id': 'parang1995',
            'title': 'parang1995 - highlight',
        },
        'playlist_count': 997,
    }, {
        'url': 'https://bj.afreecatv.com/ryuryu24/vods',
        'info_dict': {
            '_type': 'playlist',
            'id': 'ryuryu24',
            'title': 'ryuryu24 - all',
        },
        'playlist_count': 221,
    }, {
        'url': 'https://bj.afreecatv.com/ryuryu24/vods/balloonclip',
        'info_dict': {
            '_type': 'playlist',
            'id': 'ryuryu24',
            'title': 'ryuryu24 - balloonclip',
        },
        'playlist_count': 0,
    }]
    _PER_PAGE = 60

    def _fetch_page(self, user_id, user_type, page):
        page += 1
        info = self._download_json(f'https://bjapi.afreecatv.com/api/{user_id}/vods/{user_type}', user_id,
                                   query={'page': page, 'per_page': self._PER_PAGE, 'orderby': 'reg_date'},
                                   note=f'Downloading {user_type} video page {page}')
        for item in info['data']:
            yield self.url_result(
                f'https://vod.afreecatv.com/player/{item["title_no"]}/', AfreecaTVIE, item['title_no'])

    def _real_extract(self, url):
        user_id, user_type = self._match_valid_url(url).group('id', 'slug_type')
        user_type = user_type or 'all'
        entries = OnDemandPagedList(functools.partial(self._fetch_page, user_id, user_type), self._PER_PAGE)
        return self.playlist_result(entries, user_id, f'{user_id} - {user_type}')
