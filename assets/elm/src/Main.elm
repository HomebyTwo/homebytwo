module Main exposing (..)

-- Display route checkpoints
--
--

import Browser
import GeoJson
import Html exposing (..)
import Html.Attributes exposing (attribute, class)
import Http
import Json.Decode as D
import Numeral exposing (format)



-- MAIN


main =
    Browser.element
        { init = init
        , update = update
        , subscriptions = subscriptions
        , view = view
        }



-- MODEL


type Model
    = Failure Http.Error
    | Loading
    | Success (List Checkpoint)


type alias Checkpoint =
    { name : String
    , place_type : String
    , altitude : Float
    , schedule : String
    , distance : Float
    , elevationGain : Float
    , elevationLoss : Float
    , geom : GeoJson.GeoJson
    }


init : String -> ( Model, Cmd Msg )
init url =
    ( Loading, getCheckpoints url )



-- UPDATE


type Msg
    = GotCheckpoints (Result Http.Error (List Checkpoint))


update : Msg -> Model -> ( Model, Cmd Msg )
update msg model =
    case msg of
        GotCheckpoints result ->
            case result of
                Ok checkpoints ->
                    ( Success checkpoints, Cmd.none )

                Err error ->
                    ( Failure error, Cmd.none )



-- SUBSCRIPTIONS


subscriptions : Model -> Sub Msg
subscriptions model =
    Sub.none



-- VIEW


view : Model -> Html Msg
view model =
    div [] [ viewCheckpoints model ]


viewCheckpoints : Model -> Html Msg
viewCheckpoints model =
    case model of
        Failure error ->
            div []
                [ text "error" ]

        Loading ->
            div []
                [ text "Loading..." ]

        Success checkpoints ->
            div []
                [ renderCheckpoints checkpoints ]


renderCheckpoints : List Checkpoint -> Html Msg
renderCheckpoints checkpoints =
    ul [ class "list list--stacked" ] (List.map renderCheckpoint checkpoints)


renderCheckpoint : Checkpoint -> Html Msg
renderCheckpoint checkpoint =
    li [ class "box box--default box--tight mrgv- pdg- place", attribute "data-geom" "TODO" ]
        [ div [ class "grid grid--tight" ]
            [ renderCheckpointName checkpoint.name checkpoint.altitude
            , renderCheckpointSchedule checkpoint.schedule
            , renderCheckpointType checkpoint.place_type
            , renderElevationAndDistance checkpoint.distance checkpoint.elevationGain checkpoint.elevationLoss
            ]
        ]


renderCheckpointName : String -> Float -> Html Msg
renderCheckpointName name altitude =
    div
        [ class "w-2/3 sm-w-4/5 grid__item place__name" ]
        [ text <| name ++ ", "
        , text <| format "0,0.0" altitude ++ "m"
        ]


renderCheckpointSchedule : String -> Html Msg
renderCheckpointSchedule schedule =
    div
        [ class "w-1/3 sm-w-1/5 grid__item text-right" ]
        [ text schedule ]


renderCheckpointType : String -> Html Msg
renderCheckpointType place_type =
    div
        [ class "w-1/2 grid__item text-small text-left" ]
        [ text place_type ]


renderElevationAndDistance : Float -> Float -> Float -> Html Msg
renderElevationAndDistance distance elevationGain elevationLoss =
    div
        [ class "w-1/2 grid__item text-small text-right" ]
        [ text <| format "0,0.0" distance ++ "km"
        , text <| " ➚ " ++ format "0,0" elevationGain ++ "m"
        , text <| " ➘ " ++ format "0,0" elevationLoss ++ "m"
        ]



-- HTTP


getCheckpoints : String -> Cmd Msg
getCheckpoints url =
    Http.get
        { url = url
        , expect = Http.expectJson GotCheckpoints checkpointsDecoder
        }



-- JSON Decoders


checkpointsDecoder : D.Decoder (List Checkpoint)
checkpointsDecoder =
    D.field "checkpoints" (D.list checkpointDecoder)


checkpointDecoder : D.Decoder Checkpoint
checkpointDecoder =
    D.map8
        Checkpoint
        (D.field "name" D.string)
        (D.field "place_type" D.string)
        (D.field "altitude" D.float)
        (D.field "schedule" D.string)
        (D.field "distance" D.float)
        (D.field "elevation_gain" D.float)
        (D.field "elevation_loss" D.float)
        (D.field "geom" GeoJson.decoder)
