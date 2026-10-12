const apikey = "2d3d43c07a7fb4e2d3a6dd20ca5073d0";

// Geolocation-based weather search
window.addEventListener("load", () => {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition((position) => {
            let lon = position.coords.longitude;
            let lat = position.coords.latitude;
            const url = `https://api.openweathermap.org/data/2.5/weather?lat=${lat}&lon=${lon}&appid=${apikey}`;

            fetch(url).then((res) => {
                return res.json();
            }).then((data) => {
                console.log(data);
                console.log(new Date().getTime());
                var dat = new Date(data.dt * 1000);  // dt is in seconds, multiply by 1000 for milliseconds
                console.log(dat.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }));
                weatherReport(data);
            }).catch((error) => console.error("Error fetching weather data:", error));
        });
    }
});

// City-based weather search
function searchByCity() {
    var place = document.getElementById('input').value;
    
    if (!place) {
        alert('Please enter a city name');
        return;
    }

    var urlsearch = `https://api.openweathermap.org/data/2.5/weather?q=${place}&appid=${apikey}`;

    fetch(urlsearch).then((res) => {
        return res.json();
    }).then((data) => {
        console.log(data);
        weatherReport(data);
    }).catch((error) => console.error("Error fetching weather data by city:", error));
    
    document.getElementById('input').value = '';
}

// Weather report function
function weatherReport(data) {
    var urlcast = `https://api.openweathermap.org/data/2.5/forecast?q=${data.name}&appid=${apikey}`;

    fetch(urlcast).then((res) => {
        return res.json();
    }).then((forecast) => {
        console.log(forecast.city);
        hourForecast(forecast);
        dayForecast(forecast);

        document.getElementById('city').innerText = `${data.name}, ${data.sys.country}`;
        document.getElementById('temperature').innerText = Math.floor(data.main.temp - 273) + ' °C';
        document.getElementById('clouds').innerText = data.weather[0].description;

        let icon1 = data.weather[0].icon;
        let iconurl = `https://openweathermap.org/img/w/${icon1}.png`;
        document.getElementById('img').src = iconurl;
    }).catch((error) => console.error("Error fetching forecast data:", error));
}

// Hourly forecast display
function hourForecast(forecast) {
    document.querySelector('.templist').innerHTML = '';

    for (let i = 0; i < 5; i++) {
        var date = new Date(forecast.list[i].dt * 1000);
        let timeString = date.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata' }).replace(':00', '');

        let hourR = document.createElement('div');
        hourR.setAttribute('class', 'next');

        let div = document.createElement('div');
        let time = document.createElement('p');
        time.setAttribute('class', 'time');
        time.innerText = timeString;

        let temp = document.createElement('p');
        temp.innerText = Math.floor(forecast.list[i].main.temp_max - 273) + ' °C' + ' / ' + Math.floor(forecast.list[i].main.temp_min - 273) + ' °C';

        div.appendChild(time);
        div.appendChild(temp);

        let desc = document.createElement('p');
        desc.setAttribute('class', 'desc');
        desc.innerText = forecast.list[i].weather[0].description;

        hourR.appendChild(div);
        hourR.appendChild(desc);
        document.querySelector('.templist').appendChild(hourR);
    }
}

// Daily forecast display
function dayForecast(forecast) {
    document.querySelector('.weekF').innerHTML = '';

    for (let i = 8; i < forecast.list.length; i += 8) {
        let forecastData = forecast.list[i];
        let date = new Date(forecastData.dt * 1000).toDateString();

        let div = document.createElement('div');
        div.setAttribute('class', 'dayF');

        let day = document.createElement('p');
        day.setAttribute('class', 'date');
        day.innerText = date;

        let temp = document.createElement('p');
        temp.innerText = Math.floor(forecastData.main.temp_max - 273) + ' °C' + ' / ' + Math.floor(forecastData.main.temp_min - 273) + ' °C';

        let description = document.createElement('p');
        description.setAttribute('class', 'desc');
        description.innerText = forecastData.weather[0].description;

        div.appendChild(day);
        div.appendChild(temp);
        div.appendChild(description);

        document.querySelector('.weekF').appendChild(div);
    }
}
