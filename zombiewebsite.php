<!DOCTYPE html>
<html>
<head>
    <title>Zombie Scores</title>
    <meta http-equiv="refresh" content="300">
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #000080; /* navy blue */
            color: #FFF; /* text color is white */
            text-align: center; /* center text */
        }
        .score-card {
            background-color: #000033; /* dark blue */
            margin-bottom: 10px;
            padding: 10px;
            border-radius: 5px;
            color: #FF0000; /* score-card text color is red */
            text-align: center; /* center text */
        }
        .search-form {
            width: fit-content;
            margin: auto;
        }
    </style>
</head>
<body>
    <h1>Zombie Scores</h1>
    <div class="search-form">
        <form action="" method="GET">
            <input type="text" name="username" placeholder="Enter username">
            <input type="submit" value="Search">
        </form>
    </div>
    <?php
    ini_set('display_errors', 1);
    ini_set('display_startup_startup_errors', 1);
    error_reporting(E_ALL);

    $json = file_get_contents('/var/www/html/zombie/killz');

    if (empty($json)) {
        echo "<p>The JSON file is empty. Please check your JSON file and try again.</p>";
        exit();
    }

    $data = json_decode($json, true);

    if ($data === null && json_last_error() !== JSON_ERROR_NONE) {
        echo "<p>Could not read the JSON file. Please check your JSON file and try again.</</p>";
        echo "<p>Error message: " . json_last_error_msg() . "</p>";
        exit();
    }

    $scores = $data['scores'];
    arsort($scores);

    $username = isset($_GET['username']) ? htmlspecialchars($_GET['username']) : '';

    foreach ($scores as $user => $score) {
        if($username == '' || strtolower($user) == strtolower($username)) {
            echo "<div class='score-card'>";
            echo "<p>User: " . htmlspecialchars($user) . ", Score: " . htmlspecialchars($score) . "</p>";
            echo "</div>";
        }
    }
    ?>
</body>
</html>

