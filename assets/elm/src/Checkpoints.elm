module Checkpoints exposing (main)

-- Display route checkpoints
--
--

import Browser
import GeoJson exposing (GeoJson)
import Html exposing (..)
import Html.Attributes exposing (attribute, checked, class, classList, for, id, name, type_, value, width)
import Html.Events exposing (onClick)
import Http
import Json.Decode as Decode exposing (Decoder)
import Json.Decode.Pipeline exposing (required)
import Json.Encode exposing (Value)
import Numeral exposing (format)
import Set exposing (Set)



-- MAIN


main =
    Browser.element
        { init = init
        , update = update
        , subscriptions = \_ -> Sub.none
        , view = view
        }


init : Value -> ( Model, Cmd Msg )
init flags =
    case Decode.decodeValue configDecoder flags of
        Ok config ->
            ( Model config LoadingExistingCheckpoints, getCheckpoints config.displayUrl GotExistingCheckpoints )

        Err error ->
            ( Model (Config "" "" "" False) (Failure (Decode.errorToString error)), Cmd.none )



-- MODEL


type alias Model =
    { config : Config
    , status : Status
    }


type alias Config =
    { displayUrl : String
    , editUrl : String
    , csrfToken : String
    , canEdit : Bool
    }


configDecoder : Decoder Config
configDecoder =
    Decode.succeed Config
        |> required "display_url" Decode.string
        |> required "edit_url" Decode.string
        |> required "csrf_token" Decode.string
        |> required "can_edit" Decode.bool


type Status
    = Failure String
    | LoadingExistingCheckpoints
    | Display (List Checkpoint)
    | LoadingPossibleCheckpoints (List Checkpoint)
    | Edit CheckpointSelection
    | Saving


type alias CheckpointSelection =
    { checkpoints : List Checkpoint, selected : Set String }


type alias Checkpoint =
    { name : String
    , place_type : String
    , altitude : Float
    , schedule : String
    , distance : Float
    , elevationGain : Float
    , elevationLoss : Float
    , geom : GeoJson.GeoJson
    , fieldValue : String
    , saved : Bool
    }


checkpointDecoder : Decoder Checkpoint
checkpointDecoder =
    Decode.succeed Checkpoint
        |> required "name" Decode.string
        |> required "place_type" Decode.string
        |> required "altitude" Decode.float
        |> required "schedule" Decode.string
        |> required "distance" Decode.float
        |> required "elevation_gain" Decode.float
        |> required "elevation_loss" Decode.float
        |> required "geom" GeoJson.decoder
        |> required "field_value" Decode.string
        |> required "saved" Decode.bool



-- UPDATE


type Msg
    = GotExistingCheckpoints (Result Http.Error (List Checkpoint))
    | GotPossibleCheckpoints (Result Http.Error (List Checkpoint))
    | ClickedEditCheckpoints
    | ClickedSaveCheckpoints
    | SavedCheckpoints (Result Http.Error (List Checkpoint))
    | SelectedCheckpoint String
    | DeselectedCheckpoint String


update : Msg -> Model -> ( Model, Cmd Msg )
update msg model =
    case msg of
        GotExistingCheckpoints (Ok checkpoints) ->
            ( { model | status = Display checkpoints }, Cmd.none )

        GotExistingCheckpoints (Err error) ->
            ( { model | status = Failure (errorToString error) }, Cmd.none )

        GotPossibleCheckpoints (Ok checkpoints) ->
            ( { model | status = Edit { checkpoints = checkpoints, selected = setFromCheckpointList checkpoints } }, Cmd.none )

        GotPossibleCheckpoints (Err error) ->
            ( { model | status = Failure (errorToString error) }, Cmd.none )

        SavedCheckpoints (Ok checkpoints) ->
            ( { model | status = Display checkpoints }, Cmd.none )

        SavedCheckpoints (Err error) ->
            ( { model | status = Failure (errorToString error) }, Cmd.none )

        ClickedEditCheckpoints ->
            case model.status of
                Display checkpoints ->
                    ( { model | status = LoadingPossibleCheckpoints checkpoints }, getCheckpoints model.config.editUrl GotPossibleCheckpoints )

                _ ->
                    ( model, Cmd.none )

        ClickedSaveCheckpoints ->
            case model.status of
                Edit checkpointSelection ->
                    ( { model | status = Saving }, postCheckpoints model.config.editUrl model.config.csrfToken checkpointSelection.selected )

                _ ->
                    ( model, Cmd.none )

        SelectedCheckpoint fieldValue ->
            case model.status of
                Edit { checkpoints, selected } ->
                    ( { model | status = Edit (CheckpointSelection checkpoints (Set.insert fieldValue selected)) }, Cmd.none )

                _ ->
                    ( model, Cmd.none )

        DeselectedCheckpoint fieldValue ->
            case model.status of
                Edit { checkpoints, selected } ->
                    ( { model | status = Edit (CheckpointSelection checkpoints (Set.remove fieldValue selected)) }, Cmd.none )

                _ ->
                    ( model, Cmd.none )


setFromCheckpointList : List Checkpoint -> Set String
setFromCheckpointList checkpoints =
    List.filter (\checkpoint -> checkpoint.saved) checkpoints
        |> List.map (\checkpoint -> checkpoint.fieldValue)
        |> Set.fromList



-- VIEW


view : Model -> Html Msg
view model =
    div [ class "checkpoints mrgv-" ] <|
        case model.status of
            LoadingExistingCheckpoints ->
                [ text "Loading Checkpoints..." ]

            Display checkpoints ->
                [ viewDisplayCheckpoints checkpoints
                , if model.config.canEdit then
                    viewActionButton ClickedEditCheckpoints

                  else
                    text ""
                ]

            LoadingPossibleCheckpoints checkpoints ->
                [ text "Loading checkpoints.. "
                , viewDisplayCheckpoints checkpoints
                ]

            Edit checkpointSelection ->
                [ viewEditCheckpoints checkpointSelection
                , viewActionButton ClickedSaveCheckpoints
                ]

            Saving ->
                [ text "Saving Checkpoints..." ]

            Failure error ->
                [ text error ]


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
        ClickedEditCheckpoints ->
            "Add/Remove Checkpoints"

        ClickedSaveCheckpoints ->
            "Save Checkpoints"

        _ ->
            ""


viewDisplayCheckpoints : List Checkpoint -> Html Msg
viewDisplayCheckpoints checkpoints =
    case checkpoints of
        [] ->
            div [ class "box box--default box--tight mrgv- pdg- place" ]
                [ text "No checkpoint has been added to this route." ]

        _ ->
            ul [ class "list list--stacked" ] <|
                List.map viewDisplayCheckpoint checkpoints


viewDisplayCheckpoint : Checkpoint -> Html Msg
viewDisplayCheckpoint checkpoint =
    li [ class "box box--default box--tight mrgv- pdg- place", attribute "data-geom" "TODO" ]
        [ viewCheckpointInfo checkpoint ]


viewEditCheckpoints : CheckpointSelection -> Html Msg
viewEditCheckpoints checkpointSelection =
    ul [ class "list list--stacked" ] <|
        List.map (viewEditCheckpoint checkpointSelection.selected) checkpointSelection.checkpoints


viewEditCheckpoint : Set String -> Checkpoint -> Html Msg
viewEditCheckpoint selected checkpoint =
    let
        isChecked =
            Set.member checkpoint.fieldValue selected

        message =
            if isChecked then
                DeselectedCheckpoint checkpoint.fieldValue

            else
                SelectedCheckpoint checkpoint.fieldValue
    in
    li
        [ class "box box--tight mrgv- place"
        , classList [ ( "box--default", isChecked ) ]
        , attribute "data-geom" "TODO"
        ]
        [ label [ for checkpoint.fieldValue, class "label pdg0" ]
            [ table [ class "mrgv0 pdg0" ]
                [ tbody []
                    [ tr []
                        [ td [ class "text-center", width 10 ] [ viewCheckpointCheckbox message isChecked checkpoint ]
                        , td [] [ viewCheckpointInfo checkpoint ]
                        ]
                    ]
                ]
            ]
        ]


viewCheckpointInfo : Checkpoint -> Html Msg
viewCheckpointInfo checkpoint =
    div [ class "grid grid--tight" ]
        [ viewCheckpointName checkpoint.name checkpoint.altitude
        , viewCheckpointSchedule checkpoint.schedule
        , viewCheckpointType checkpoint.place_type
        , viewElevationAndDistance checkpoint.distance checkpoint.elevationGain checkpoint.elevationLoss
        ]


viewCheckpointName : String -> Float -> Html Msg
viewCheckpointName name altitude =
    div
        [ class "w-2/3 sm-w-4/5 grid__item place__name" ]
        [ text <| name ++ ", "
        , text <| format "0,0" altitude ++ "m"
        ]


viewCheckpointCheckbox : Msg -> Bool -> Checkpoint -> Html Msg
viewCheckpointCheckbox message isChecked checkpoint =
    input
        [ id checkpoint.fieldValue
        , type_ "checkbox"
        , class "checkbox"
        , value checkpoint.fieldValue
        , checked isChecked
        , onClick message
        ]
        []


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


getCheckpoints url msg =
    Http.get
        { url = url
        , expect = Http.expectJson msg checkpointsDecoder
        }


postCheckpoints : String -> String -> Set String -> Cmd Msg
postCheckpoints url csrftoken selected =
    let
        body =
            [ Http.stringPart "csrfmiddlewaretoken" csrftoken ]
                ++ List.map (Http.stringPart "checkpoints") (Set.toList selected)
                |> Http.multipartBody
    in
    Http.post
        { url = url
        , body = body
        , expect = Http.expectJson GotExistingCheckpoints checkpointsDecoder
        }


errorToString : Http.Error -> String
errorToString error =
    case error of
        Http.BadUrl url ->
            "The URL " ++ url ++ " was invalid"

        Http.Timeout ->
            "Unable to reach the server, try again"

        Http.NetworkError ->
            "Unable to reach the server, check your network connection"

        Http.BadStatus 500 ->
            "The server had a problem, try again later."

        Http.BadStatus 400 ->
            "Verify your information and try again"

        Http.BadStatus _ ->
            "Unknown error"

        Http.BadBody errorMessage ->
            errorMessage



-- JSON Decoders


checkpointsDecoder : Decoder (List Checkpoint)
checkpointsDecoder =
    Decode.field "checkpoints" <| Decode.list checkpointDecoder
