port module Main exposing (main)

import Browser
import Html exposing (..)
import Html.Attributes exposing (checked, class, classList, for, id, name, type_, value, width)
import Html.Events exposing (onClick)
import Http exposing (Error)
import Json.Decode as Decode exposing (Decoder)
import Json.Decode.Pipeline exposing (custom, required)
import Json.Encode as Encode exposing (Value)
import Numeral exposing (format)
import Set exposing (Set)



-- MAIN


main =
    Browser.element
        { init = init
        , update = update
        , subscriptions = subscriptions
        , view = view
        }


init : Config -> ( Model, Cmd Msg )
init config =
    let
        url =
            config.displayUrl

        cmd =
            getSchedule url GotSchedule

        model =
            { config = config, status = LoadingSchedule }
    in
    ( model, cmd )


subscriptions : Model -> Sub Msg
subscriptions _ =
    clickedPlace ClickedCheckpoint



-- Model


type Status
    = Failure String
    | LoadingSchedule
    | DisplaySchedule Schedule
