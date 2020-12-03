module Checkpoints exposing (main)

-- Display route checkpoints
--
--

import Browser
import GeoJson exposing (GeoJson)
import Html exposing (..)
import Html.Attributes exposing (attribute, class, classList, for, id, name, type_, value)
import Html.Events exposing (onClick)
import Http
import Json.Decode as Decode exposing (Decoder)
import Json.Decode.Pipeline exposing (hardcoded, optional, required)
import Numeral exposing (format)



-- MAIN


main =
    Browser.element
        { init = init
        , update = update
        , subscriptions = \_ -> Sub.none
        , view = view
        }


init : String -> ( Model, Cmd Msg )
init endpoint_url =
    ( Model (Config endpoint_url) Loading, getCheckpoints endpoint_url )



-- MODEL


type alias Model =
    { config : Config
    , status : Status
    }


type alias Config =
    { endpoint_url : String }


type Status
    = Failure Http.Error
    | Loading
    | Display (List Checkpoint)
    | Edit (List Checkpoint)
    | Saving


type alias Checkpoint =
    { fieldValue : String
    , name : String
    , place_type : String
    , altitude : Float
    , schedule : String
    , distance : Float
    , elevationGain : Float
    , elevationLoss : Float
    , geom : GeoJson.GeoJson
    }



-- UPDATE


type Msg
    = GotCheckpoints (Result Http.Error (List Checkpoint))
    | EditCheckpoints
    | SaveCheckpoints
    | SavedCheckpoints (Result Http.Error (List Checkpoint))


update : Msg -> Model -> ( Model, Cmd Msg )
update msg model =
    case msg of
        GotCheckpoints (Ok checkpoints) ->
            ( { model | status = Display checkpoints }, Cmd.none )

        GotCheckpoints (Err error) ->
            ( { model | status = Failure error }, Cmd.none )

        SavedCheckpoints (Ok checkpoints) ->
            ( { model | status = Display checkpoints }, Cmd.none )

        SavedCheckpoints (Err error) ->
            ( { model | status = Failure error }, Cmd.none )

        EditCheckpoints ->
            case model.status of
                Display checkpoints ->
                    ( { model | status = Edit checkpoints }, Cmd.none )

                _ ->
                    ( model, Cmd.none )

        SaveCheckpoints ->
            case model.status of
                Edit checkpoints ->
                    ( { model | status = Saving }, postCheckpoints model.config.endpoint_url checkpoints )

                _ ->
                    ( model, Cmd.none )



-- VIEW


view : Model -> Html Msg
view model =
    div []
        [ viewCheckpoints model.status
        , viewActionButtons model.status
        ]


viewActionButtons : Status -> Html Msg
viewActionButtons status =
    case status of
        Display _ ->
            viewActionButton EditCheckpoints

        Edit _ ->
            viewActionButton SaveCheckpoints

        _ ->
            text ""


viewActionButton : Msg -> Html Msg
viewActionButton message =
    div [ class "grid grid--multiline grid--center grid--small" ]
        [ div [ class "grid__item" ]
            [ button
                [ class "btn btn--secondary btn--block"
                , onClick message
                ]
                [ text (messageToString message) ]
            ]
        ]


messageToString : Msg -> String
messageToString message =
    case message of
        EditCheckpoints ->
            "Edit Checkpoints"

        SaveCheckpoints ->
            "Save Checkpoints"

        _ ->
            ""


viewCheckpoints : Status -> Html Msg
viewCheckpoints status =
    case status of
        Loading ->
            text "Loading Checkpoints..."

        Display checkpoints ->
            viewDisplayCheckpoints checkpoints

        Edit checkpoints ->
            viewEditCheckpoints checkpoints

        Saving ->
            text "Saving Checkpoints..."

        Failure error ->
            text "error"


viewDisplayCheckpoints : List Checkpoint -> Html Msg
viewDisplayCheckpoints checkpoints =
    ul [ class "list list--stacked" ] <|
        List.map viewDisplayCheckpoint checkpoints


viewDisplayCheckpoint : Checkpoint -> Html Msg
viewDisplayCheckpoint checkpoint =
    li [ class "box box--default box--tight mrgv- pdg- place", attribute "data-geom" "TODO" ]
        [ div [ class "grid grid--tight" ]
            [ viewCheckpointName checkpoint.name checkpoint.altitude
            , viewCheckpointSchedule checkpoint.schedule
            , viewCheckpointType checkpoint.place_type
            , viewElevationAndDistance checkpoint.distance checkpoint.elevationGain checkpoint.elevationLoss
            ]
        ]


viewEditCheckpoints : List Checkpoint -> Html Msg
viewEditCheckpoints checkpoints =
    ul [ class "list list--stacked" ] <|
        List.map viewEditCheckpoint checkpoints


viewEditCheckpoint : Checkpoint -> Html Msg
viewEditCheckpoint checkpoint =
    li
        [ class "box box--tight mrgv- pdg- place"
        , classList [ ( "box--default", True ) ]
        , attribute "data-geom" "TODO"
        ]
        [ label [ for checkpoint.fieldValue ]
            [ div [ class "grid grid--tight" ]
                [ viewCheckpointCheckbox checkpoint
                , viewCheckpointSchedule checkpoint.schedule
                , viewCheckpointType checkpoint.place_type
                , viewElevationAndDistance checkpoint.distance checkpoint.elevationGain checkpoint.elevationLoss
                ]
            ]
        ]


viewCheckpointName : String -> Float -> Html Msg
viewCheckpointName name altitude =
    div
        [ class "w-2/3 sm-w-4/5 grid__item place__name" ]
        [ text <| name ++ ", "
        , text <| format "0,0.0" altitude ++ "m"
        ]


viewCheckpointCheckbox : Checkpoint -> Html Msg
viewCheckpointCheckbox checkpoint =
    div
        [ class "w-2/3 sm-w-4/5 grid__item place__name" ]
        [ input [ id checkpoint.fieldValue, type_ "checkbox", class "checkbox", value checkpoint.fieldValue ] []
        , text <| checkpoint.name ++ ", "
        , text <| format "0,0.0" checkpoint.altitude ++ "m"
        ]


viewCheckpointSchedule : String -> Html Msg
viewCheckpointSchedule schedule =
    div
        [ class "w-1/3 sm-w-1/5 grid__item text-right" ]
        [ text schedule ]


viewCheckpointType : String -> Html Msg
viewCheckpointType place_type =
    div
        [ class "w-1/2 grid__item text-small text-left" ]
        [ text place_type ]


viewElevationAndDistance : Float -> Float -> Float -> Html Msg
viewElevationAndDistance distance elevationGain elevationLoss =
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


postCheckpoints : String -> List Checkpoint -> Cmd Msg
postCheckpoints url checkpoints =
    Http.post
        { url = url
        , body = Http.emptyBody
        , expect = Http.expectJson GotCheckpoints checkpointsDecoder
        }



-- JSON Decoders


checkpointsDecoder : Decoder (List Checkpoint)
checkpointsDecoder =
    Decode.field "checkpoints" <| Decode.list checkpointDecoder


checkpointDecoder : Decoder Checkpoint
checkpointDecoder =
    Decode.succeed Checkpoint
        |> required "field_value" Decode.string
        |> required "name" Decode.string
        |> required "place_type" Decode.string
        |> required "altitude" Decode.float
        |> required "schedule" Decode.string
        |> required "distance" Decode.float
        |> required "elevation_gain" Decode.float
        |> required "elevation_loss" Decode.float
        |> required "geom" GeoJson.decoder



-- JSON Encoders
