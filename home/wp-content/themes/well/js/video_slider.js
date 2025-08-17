if (
  // !navigator.userAgent.match(
  //   /(iPod|iPhone|iPad|Android|webOS|BlackBerry|Windows Phone)/
  // )
  true
) {
  var tag = document.createElement("script");
  tag.src = "https://www.youtube.com/player_api";
  var firstScriptTag = document.getElementsByTagName("script")[0];
  firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);
  var playerDefaults = {
    autoplay: 0,
    autohide: 1,
    modestbranding: 0,
    rel: 0,
    showinfo: 0,
    controls: 0,
    disablekb: 1,
    enablejsapi: 1,
    iv_load_policy: 3,
    loop: 1
  };

  var playerInfoList = JSON.parse(video_data);
  var autoPlay = (flkty_setting.autoplay) ? 8000 : false;
  var players = [];
  var flkty = new Flickity(".hero-carousel", {
    "cellAlign": "left",
    "contain": true,
    "adaptiveHeight": true,
    "lazyLoad": true,
    "wrapAround": true,
    "autoPlay": autoPlay
  });
  
  var playerIndex = 0; // starting on the first slide on page load
  var prevIndex = 0;
  var currentIndex = 0;

  if (playerInfoList[currentIndex] != false) {
    var sId = playerInfoList[playerIndex].id;
    var sId = "#" + sId;
    setTimeout(function () { jQuery(sId).addClass("active") }, 1000);
    currentIndex = flkty.selectedIndex;
  } else {
    currentIndex = flkty.selectedIndex;
  }

  flkty.on("change", function () {
    if (playerInfoList[currentIndex]) {
      players[currentIndex].stopVideo();
    }

    if (jQuery(".is-selected").children("div.tv").length > 0) {
      sId = playerInfoList[currentIndex].id;
      sId = "#" + sId;
      jQuery(sId).removeClass("active");
    }
    currentIndex = flkty.selectedIndex;

    if (playerInfoList[currentIndex] != false) {
      sId = "#" + playerInfoList[currentIndex].id;
      jQuery(sId).addClass("active");
      players[currentIndex].playVideo();
    }

    if (playerInfoList[currentIndex]) {
      sId = "#" + playerInfoList[currentIndex].id;
      jQuery(sId).addClass("active");
    }
  });
}

function onYouTubeIframeAPIReady() {
  if (typeof playerInfoList === "undefined") return;

  for (var i = 0; i < playerInfoList.length; i++) {
    var curplayer = createPlayer(playerInfoList[i]);
    players[i] = curplayer;
  }
}

function createPlayer(playerInfo) {
  if (playerInfo != false) {
    return new YT.Player(playerInfo.id, {
      height: playerInfo.height,
      width: playerInfo.width,
      videoId: playerInfo.videoId,
      events: {
        onReady: onPlayerReady,
        onStateChange: onPlayerStateChange
      },
      playerVars: playerDefaults
    });
  } else {
    return false;
  }
}

jQuery(".video-controls").on("click", ".mute", function () {
  console.log(players);
  if (players[currentIndex].isMuted()) {
    players[currentIndex].unMute();
    jQuery(this).removeClass("hero-volume-on");
    jQuery(this).addClass("hero-volume-off");
  } else {
    players[currentIndex].mute();
    jQuery(this).removeClass("hero-volume-off");
    jQuery(this).addClass("hero-volume-on");
  }
});

jQuery(".video-controls").on("click", ".pause", function () {
  if (players[currentIndex].getPlayerState() === 1) {
    players[currentIndex].pauseVideo();
    jQuery(this).removeClass("hero-pause");
    jQuery(this).addClass("hero-play");
  } else if (players[currentIndex].getPlayerState() === 2) {
    players[currentIndex].playVideo();
    jQuery(this).removeClass("hero-play");
    jQuery(this).addClass("hero-pause");
  }
});

function onPlayerReady(i) {
  i.target.stopVideo();
  i.target.mute();
  if (playerInfoList[0] != false) {
    players[0].playVideo();
  }
}

function onPlayerStateChange(e) {
  if (e.data === YT.PlayerState.ENDED) {
    e.target.playVideo();
  }
}
