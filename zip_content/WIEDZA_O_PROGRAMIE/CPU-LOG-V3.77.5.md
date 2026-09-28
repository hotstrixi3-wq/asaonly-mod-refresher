# V3.77.5 — łamanie wpisów CPU

Szczegółowy wpis stanu CPU jest celowo dzielony po aktualnym affinity i przed celem. Drugi wiersz zaczyna się od `↳ cel:`, dzięki czemu długie listy logicznych CPU nie sklejają aktualnego stanu, celu i decyzji w jedną linię.

Testy automatyczne: 47/47 PASS.
