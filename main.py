from nicegui import ui
import random
import string

rooms = {}


def generateRoomCode():
    # Generate a short, shareable room code.
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

@ui.page('/')
def home():
    # Home screen: create or join a game room.
    ui.label('Welcome to Guess the DJ').classes('text-3xl')

    # Create room form.
    name_input = ui.input('Enter your name')

    def createRoom():
        player_name = (name_input.value or '').strip()
        if not player_name:
            ui.notify('Please enter your name')
            return

        roomCode = generateRoomCode()
        while roomCode in rooms:
            roomCode = generateRoomCode()

        rooms[roomCode] = {
            'host': player_name,
            'DJ': player_name,

            'players': [],
            'submissions': {},
            'guesses': {},
            'scores': {},

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


@ui.page('/room/{roomCode}')
def room(roomCode: str):
    # Room screen: shared game state + per-player UI.
    playerName = ui.context.client.request.query_params.get('name', 'Unknown')

    if roomCode not in rooms:
        ui.label('Room not found')
        return

    room_state = rooms[roomCode]
    # Backfill optional keys for older room objects.
    room_state.setdefault('scores', {})
    room_state.setdefault('guesses', {})

    playerExists = any (
        player ['name'] == playerName
        for player in room_state['players']
    )

    if not playerExists:
        role = 'Player' 
        if playerName == room_state['host']:
            role = 'host / DJ'

        room_state['players'].append ({
                'name': playerName,
                'role': role
            })
        room_state['scores'][playerName] = 0

    ui.label(f'Room Code: {roomCode}').classes('text-2xl')
    gameArea = ui.column()

    # Live readiness indicator (song submissions or guess submissions vs players).
    readyLabel = ui.label('0 / 0 Players Ready')

    def updateReadyLabel():
        playerCount = len(room_state['players'])
        if room_state.get('gameState') == 'GUESSING':
            submittedCount = len(room_state.get('guess_submissions', {}))
        else:
            submittedCount = len(room_state['submissions'])

        readyLabel.set_text(
            f'{submittedCount} / {playerCount} Players Ready'
        )

    ui.timer(1, updateReadyLabel)


    playerColumn = ui.column()

    def calculateScores():
        for guesser_name, guesses in room_state['guesses'].items():
            for actual_submitter, guessed_player in guesses.items():
                if guessed_player == actual_submitter:
                    room_state['scores'][guesser_name] += 1
                    room_state['scores'][actual_submitter] += 1

    # Build all game-state areas once; visibility is toggled by refreshGameUI.
    with gameArea:
        # Lobby area: host starts the round.
        lobbyArea = ui.column()
        with lobbyArea:
            ui.label('Waiting in Lobby')

            def startGame():
                room_state['gameState'] = 'SONG_SELECTION'
                refreshGameUI()

            if playerName == room_state['host']:
                ui.button('Start Game', on_click=startGame)

        # Song selection area: each player submits one song.
        songArea = ui.column()
        with songArea:
            ui.label('Submit a song')
            songInput = ui.input('Enter song name')

            def submitSong():
                song_name = (songInput.value or '').strip()

                if not song_name:
                    ui.notify('Please enter a song name')
                    return
                
                room_state['submissions'][playerName] = song_name

                ui.notify('Song Submitted!')

                updateReadyLabel()

                if len(room_state['submissions']) == len(room_state['players']):
                    room_state['gameState'] = 'GUESSING'
                    refreshGameUI()

            ui.button(
                'Submit Song',
                on_click=submitSong
            )



        # Guessing area: players guess which player submitted each song.
        guessingArea = ui.column()
        guessSubmitArea = ui.column()
        last_guessing_signature = None

        def renderGuessingUI():
            guessingArea.clear()
            with guessingArea:
                ui.label('Guess who submitted each song')

                songs = list(room_state['submissions'].items())
                if not songs:
                    ui.label('No songs submitted yet.')
                    return

                player_guesses = room_state['guesses'].setdefault(playerName, {})
                player_options = [p['name'] for p in room_state['players']]

                for submitter, song_name in songs:
                    # Use submitter as stable key; song names can collide.
                    guess_key = submitter
                    select = ui.select(
                        options=player_options,
                        label=f'Who submitted "{song_name}"?',
                        value=player_guesses.get(guess_key),
                    ).props('outlined standout').classes('w-64 bg-white text-black')

                    select.on_value_change(
                        lambda e, key=guess_key: player_guesses.__setitem__(key, e.value)
                    )

        def submitGuesses():
            room_state.setdefault('guess_submissions', {})
            room_state['guess_submissions'][playerName] = True
            updateReadyLabel()

            if len(room_state['guess_submissions']) == len(room_state['players']):
                calculateScores()
                room_state['gameState'] = 'RESULTS'
                refreshGameUI()

        with guessSubmitArea:
            ui.button('Submit Guesses', on_click=submitGuesses)

        resultsArea = ui.column()

        def renderResultsUI():
            resultsArea.clear()
            with resultsArea:
                ui.label('Round Results').classes('text-2xl')
                for submitter, song in room_state['submissions'].items():
                    ui.label(f'{submitter} submitted: {song}')

                ui.separator()
                ui.label('Scores').classes('text-xl')

                sorted_scores = sorted(
                    room_state['scores'].items(),
                    key=lambda x: x[1],
                    reverse=True
                )
                for player, score in sorted_scores:
                    ui.label(f'{player}: {score} points')

                if playerName == room_state['host']:
                    def nextRound():
                        room_state['submissions'] = {}
                        room_state['guesses'] = {}
                        room_state['guess_submissions'] = {}
                        room_state['gameState'] = 'SONG_SELECTION'
                        updateReadyLabel()
                        refreshGameUI()

                    ui.button('Start Next Round', on_click=nextRound)

        def compute_guessing_signature():
            # Track only data that should trigger a UI rebuild.
            songs = tuple(sorted(room_state['submissions'].items()))
            player_options = tuple(sorted(p['name'] for p in room_state['players']))
            return songs, player_options

        def refreshGuessingUIIfNeeded():
            nonlocal last_guessing_signature
            signature = compute_guessing_signature()
            if signature == last_guessing_signature:
                return
            last_guessing_signature = signature
            renderGuessingUI()

    def refreshGameUI():
        # Keep every client in sync with the current game phase.
        in_lobby = room_state['gameState'] == 'LOBBY'
        in_song_selection = room_state['gameState'] == 'SONG_SELECTION'
        in_guessing = room_state['gameState'] == 'GUESSING'
        in_results = room_state['gameState'] == 'RESULTS'
        lobbyArea.set_visibility(in_lobby)
        songArea.set_visibility(in_song_selection)
        guessingArea.set_visibility(in_guessing)
        guessSubmitArea.set_visibility(in_guessing)
        resultsArea.set_visibility(in_results)
        if in_guessing:
            room_state.setdefault('guess_submissions', {})
            refreshGuessingUIIfNeeded()
            updateReadyLabel()
        if in_results:
            renderResultsUI()

    def refreshPlayers():
        # Re-render the player list so joins are reflected live.
        playerColumn.clear()

        with playerColumn:
            ui.label('Players:')

            for player in room_state['players']:
                ui.label(
                    f"{player['name']} - {player['role']}"
                )

    refreshPlayers()

    # Poll shared state so all clients stay synchronized.
    ui.timer(1, refreshPlayers)
    ui.timer(1, refreshGameUI)

    refreshGameUI()


    


ui.run(host='0.0.0.0', port=8080)

       
        

        
