from nicegui import ui
import random
import string
from prompts import prompts
from spotify import ( 
    search_song,
    clear_playlist,
    add_song_to_playlist
)

def get_random_prompt():
    return random.choice(prompts)

def is_host(room_state, playerName):
    return playerName == room_state['host']

rooms = {}


def generateRoomCode():
    # Generate a short, shareable room code.
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

@ui.page('/')
def home():
    # Home screen: create or join a game room.
    ui.label('Welcome to Guess the DJ').classes('text-3xl')
    
    def reset_shared_playlist():
        if not clear_playlist():
            ui.notify('Could not reset Spotify playlist. Check Spotify auth and playlist ID.')
            return False
        return True

    # Create room form.
    name_input = ui.input('Enter your name')

    def createRoom():
        player_name = (name_input.value or '').strip()
        if not player_name:
            ui.notify('Please enter your name')
            return
        if not reset_shared_playlist():
            return

        roomCode = generateRoomCode()
        while roomCode in rooms:
            roomCode = generateRoomCode()

        rooms[roomCode] = {
            'host': player_name,

            'players': [],
            'submissions': {},
            'guesses': {},
            'scores': {},
            'current_prompt': None,

            'gameState': 'LOBBY'
        }

        ui.navigate.to(f'/room/{roomCode}?name={player_name}')

    ui.button('Create Room', on_click=createRoom)

    # Join room form.
    ui.separator()

    ui.label('Join an existing room')

    joinNameInput = ui.input('Enter your name')
    joinRoomCodeInput = ui.input('Enter room code')

    def joinRoom():
        player_name = (joinNameInput.value or '').strip()
        roomCode_raw = (joinRoomCodeInput.value or '').strip()

        if not player_name:
            ui.notify('Please enter your name')
            return

        if not roomCode_raw:
            ui.notify('Please enter a room code')
            return

        roomCode = roomCode_raw.upper()

        if roomCode not in rooms:
            ui.notify('Room not found')
            return

        ui.navigate.to(
            f'/room/{roomCode}?name={player_name}'
        )

    ui.button('Join Room', on_click=joinRoom)


#Song Searching Functionality


@ui.page('/room/{roomCode}')
def room(roomCode: str):
    playerName = ui.context.client.request.query_params.get('name', 'Unknown')
    if roomCode not in rooms:
        ui.label('Room not found')
        return

    room_state = rooms[roomCode]
    room_state.setdefault('scores', {})
    room_state.setdefault('guesses', {})
    room_state.setdefault('submissions', {})
    room_state.setdefault('guess_submissions', {})
    room_state.setdefault('current_prompt', None)
    room_state.setdefault('shuffled_songs', None)
    room_state.setdefault('gameState', 'LOBBY')

    player_exists = any(player['name'] == playerName for player in room_state['players'])
    if not player_exists:
        role = 'host / DJ' if playerName == room_state['host'] else 'Player'
        room_state['players'].append({'name': playerName, 'role': role})
        room_state['scores'].setdefault(playerName, 0)

    is_current_host = is_host(room_state, playerName)

    def participant_names():
        return [p['name'] for p in room_state['players'] if p['name'] != room_state['host']]

    def start_round():
        if not clear_playlist():
            ui.notify('Could not reset Spotify playlist. Check Spotify auth and playlist ID.')
            return
        room_state['current_prompt'] = get_random_prompt()
        room_state['submissions'] = {}
        room_state['guesses'] = {}
        room_state['guess_submissions'] = {}
        room_state['shuffled_songs'] = None
        room_state['gameState'] = 'SONG_SELECTION'

    def calculate_scores():
        for guesser_name, guesses in room_state['guesses'].items():
            if guesser_name == room_state['host']:
                continue
            for actual_submitter, guessed_player in guesses.items():
                if guessed_player == actual_submitter:
                    room_state['scores'][guesser_name] = room_state['scores'].get(guesser_name, 0) + 1
                    if actual_submitter != room_state['host']:
                        room_state['scores'][actual_submitter] = room_state['scores'].get(actual_submitter, 0) + 1

    ui.label(f'Room Code: {roomCode}').classes('text-2xl')
    prompt_label = ui.label('')
    ready_label = ui.label('0 / 0 Players Ready')

    players_box = ui.column()
    host_panel = ui.column()
    lobby_area = ui.column()
    song_area = ui.column()
    guessing_area = ui.column()
    results_area = ui.column()

    selected_song_data = None
    player_guesses = room_state['guesses'].setdefault(playerName, {})

    with lobby_area:
        ui.label('Waiting in Lobby')
        if is_current_host:
            ui.button('Start Game', on_click=lambda: (start_round(), refresh_ui()))

    with song_area:
        ui.label('Submit a song')
        search_input = ui.input('Search Songs')
        results_column = ui.column()
        selected_song_label = ui.label('No song selected yet')

        def select_song(song):
            nonlocal selected_song_data
            selected_song_data = song
            selected_song_label.set_text(
                f'Selected: {song.get("name", "Unknown song")} - {song.get("artist", "Unknown artist")}'
            )

        def do_search():
            query = (search_input.value or '').strip()
            results_column.clear()
            if not query:
                ui.notify('Please enter a song to search')
                return

            songs = search_song(query)
            for song in songs:
                with results_column:
                    with ui.row().classes('items-center gap-3'):
                        if song.get('image'):
                            ui.image(song['image']).style('width: 64px; height: 64px')
                        with ui.column():
                            ui.label(song.get('name') or 'Unknown song').classes('text-lg font-bold')
                            ui.label(song.get('artist') or 'Unknown artist').classes('text-sm text-gray-500')
                        if song.get('url'):
                            ui.link('Open', song['url'])
                        ui.button('Select', on_click=lambda _, s=song: select_song(s))

        ui.button('Search', on_click=do_search)

        def submit_song():
            nonlocal selected_song_data
            if is_current_host:
                ui.notify('Host/DJ does not submit songs.')
                return
            if playerName in room_state['submissions']:
                ui.notify('You already submitted a song.')
                return
            if not selected_song_data:
                ui.notify('Please search and select a song first.')
                return

            song_data = selected_song_data
            add_song_to_playlist(song_data.get('uri'))
            room_state['submissions'][playerName] = {
                'name': song_data.get('name') or 'Unknown song',
                'artist': song_data.get('artist') or 'Unknown artist',
                'image': song_data.get('image'),
                'url': song_data.get('url'),
                'uri': song_data.get('uri'),
            }
            selected_song_data = None
            selected_song_label.set_text('No song selected yet')
            results_column.clear()
            ui.notify('Song submitted!')

            target = len(participant_names())
            if target > 0 and len(room_state['submissions']) >= target:
                room_state['shuffled_songs'] = random.sample(
                    list(room_state['submissions'].items()),
                    len(room_state['submissions']),
                )
                room_state['gameState'] = 'GUESSING'
            refresh_ui()

        submit_song_button = ui.button('Submit Song', on_click=submit_song)

    guess_submit_area = ui.column()
    with guess_submit_area:
        def submit_guesses():
            if is_current_host:
                ui.notify('Host/DJ does not submit guesses.')
                return
            already_submitted = playerName in room_state.get('guess_submissions', {})
            if already_submitted:
                ui.notify('You already submitted your guesses.')
                return

            songs = room_state.get('shuffled_songs') or []
            missing_guesses = [
                submitter for submitter, _ in songs
                if not player_guesses.get(submitter)
            ]
            if missing_guesses:
                ui.notify('Please submit a guess for every song before submitting.')
                return

            room_state.setdefault('guess_submissions', {})
            room_state['guess_submissions'][playerName] = True

            target = len(participant_names())
            if target > 0 and len(room_state['guess_submissions']) >= target:
                calculate_scores()
                room_state['gameState'] = 'RESULTS'
            refresh_ui()

        submit_guesses_button = ui.button('Submit Guesses', on_click=submit_guesses)

    last_game_state = None
    last_guessing_signature = None

    def render_players():
        players_box.clear()
        with players_box:
            ui.label('Players:')
            for player in room_state['players']:
                ui.label(f"{player['name']} - {player['role']}")

    def render_host_panel():
        host_panel.clear()
        if not is_current_host:
            return
        with host_panel:
            ui.label('Host / DJ Controls').classes('text-xl')
            ui.label(f"Current State: {room_state.get('gameState')}")
            if room_state.get('current_prompt'):
                ui.label(f"Prompt: {room_state['current_prompt']}")

            if room_state['gameState'] == 'LOBBY':
                ui.button('Start Game', on_click=lambda: (start_round(), refresh_ui()))
            if room_state['gameState'] == 'RESULTS':
                ui.button('Start Next Round', on_click=lambda: (start_round(), refresh_ui()))

            ui.separator()
            ui.label('Submissions (Host only):')
            if not room_state['submissions']:
                ui.label('No submissions yet.')
            for submitter, song in room_state['submissions'].items():
                with ui.row().classes('items-center gap-3'):
                    ui.label(f"{submitter}: {song.get('name', 'Unknown song')} - {song.get('artist', 'Unknown artist')}")
                    if song.get('url'):
                        ui.link('Play/Open', song['url'])

    def render_guessing():
        guessing_area.clear()
        with guessing_area:
            ui.label('Guess who submitted each song')
            songs = room_state.get('shuffled_songs') or []
            if not songs:
                ui.label('No songs available yet.')
                return

            if is_current_host:
                ui.label('Host is observing this phase.')
                return

            options = participant_names()
            for submitter, song in songs:
                guess_key = submitter
                display_name = f'{song.get("name", "Unknown song")} - {song.get("artist", "Unknown artist")}'
                select = ui.select(
                    options=options,
                    label=f'{display_name}',
                    value=player_guesses.get(guess_key),
                ).props('outlined').classes('w-full max-w-2xl')
                if playerName in room_state.get('guess_submissions', {}):
                    select.disable()
                else:
                    select.on_value_change(lambda e, key=guess_key: player_guesses.__setitem__(key, e.value))

    def render_results():
        results_area.clear()
        with results_area:
            ui.label('Round Results').classes('text-2xl')
            for submitter, song in room_state['submissions'].items():
                ui.label(f'{submitter} submitted: {song.get("name", "Unknown song")} - {song.get("artist", "Unknown artist")}')
            ui.separator()
            ui.label('Scores').classes('text-xl')
            filtered_scores = [
                (player, score)
                for player, score in room_state['scores'].items()
                if player != room_state['host']
            ]
            for player, score in sorted(filtered_scores, key=lambda x: x[1], reverse=True):
                ui.label(f'{player}: {score} points')

    def refresh_ui():
        nonlocal last_game_state, last_guessing_signature
        in_lobby = room_state['gameState'] == 'LOBBY'
        in_song_selection = room_state['gameState'] == 'SONG_SELECTION'
        in_guessing = room_state['gameState'] == 'GUESSING'
        in_results = room_state['gameState'] == 'RESULTS'

        prompt = room_state.get('current_prompt')
        prompt_label.set_text(f'Prompt: {prompt}' if (prompt and not in_lobby) else '')

        target_players = len(participant_names())
        if in_guessing:
            ready_count = len(room_state.get('guess_submissions', {}))
        else:
            ready_count = len(room_state.get('submissions', {}))
        ready_label.set_text(f'{ready_count} / {target_players} Players Ready')

        lobby_area.set_visibility(in_lobby)
        song_area.set_visibility(in_song_selection and (not is_current_host))
        guessing_area.set_visibility(in_guessing)
        guess_submit_area.set_visibility(in_guessing and (not is_current_host))
        results_area.set_visibility(in_results)

        submit_song_button.set_enabled(
            in_song_selection and (not is_current_host) and (playerName not in room_state['submissions'])
        )
        search_input.set_enabled(
            in_song_selection and (not is_current_host) and (playerName not in room_state['submissions'])
        )
        selected_song_label.set_visibility(in_song_selection and (not is_current_host))
        submit_guesses_button.set_enabled(playerName not in room_state.get('guess_submissions', {}))

        render_players()
        render_host_panel()
        guessing_signature = (
            tuple(
                (submitter, song.get('name'), song.get('artist'))
                for submitter, song in (room_state.get('shuffled_songs') or [])
            ),
            tuple(sorted(participant_names())),
            bool(playerName in room_state.get('guess_submissions', {})),
        )
        if in_guessing:
            if last_game_state != room_state['gameState'] or guessing_signature != last_guessing_signature:
                render_guessing()
                last_guessing_signature = guessing_signature
        else:
            if last_game_state == 'GUESSING':
                guessing_area.clear()
            last_guessing_signature = None
        if in_results:
            render_results()
        elif last_game_state == 'RESULTS':
            results_area.clear()

        last_game_state = room_state['gameState']

    ui.timer(1, refresh_ui)
    refresh_ui()

ui.run(host='0.0.0.0', port=8080)
