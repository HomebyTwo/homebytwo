module Checkpoints exposing (main)

-- Display route checkpoints
--
--

import Browser
import GeoJson exposing (GeoJson)
import Html exposing (..)
import Html.Attributes exposing (attribute, checked, class, classList, for, id, name, type_, value, width)
import Html.Events exposing (onClick)
import Http exposing (Error)
import Json.Decode as Decode exposing (Decoder)
import Json.Decode.Pipeline exposing (custom, required)
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


type Status
    = Failure String
    | LoadingSchedule
    | DisplaySchedule Schedule
    | LoadingPossibleSchedule Schedule
    | EditCheckpoints PossibleSchedule
    | SavingCheckpoints Schedule


type alias Schedule =
    { checkpoints : List CheckpointPlace, start : Place, finish : Place }


scheduleDecoder : Decoder Schedule
scheduleDecoder =
    Decode.succeed Schedule
        |> required "checkpoints" (Decode.list checkpointDecoder)
        |> required "start" placeDecoder
        |> required "finish" placeDecoder


type alias PossibleSchedule =
    { checkpoints : List CheckpointPlace, selected : Set FieldValue, start : Place, finish : Place }


type alias CheckpointPlace =
    { place : Place, fieldValue : FieldValue, saved : Bool }


type alias FieldValue =
    String


checkpointDecoder : Decoder CheckpointPlace
checkpointDecoder =
    Decode.succeed CheckpointPlace
        |> custom placeDecoder
        |> required "field_value" Decode.string
        |> required "saved" Decode.bool


type alias Place =
    { name : String
    , placeType : String
    , altitude : Float
    , schedule : String
    , distance : Float
    , elevationGain : Float
    , elevationLoss : Float
    , geom : GeoJson.GeoJson
    }


type PlaceType
    = Start
    | Finish
    | Checkpoint


type alias Start =
    Place


type alias Finish =
    Place


placeDecoder : Decoder Place
placeDecoder =
    Decode.succeed Place
        |> required "name" Decode.string
        |> required "place_type" Decode.string
        |> required "altitude" Decode.float
        |> required "schedule" Decode.string
        |> required "distance" Decode.float
        |> required "elevation_gain" Decode.float
        |> required "elevation_loss" Decode.float
        |> required "geom" GeoJson.decoder



-- UPDATE


type Msg
    = ClickedRetry
    | GotSchedule (Result Http.Error Schedule)
    | GotPossibleSchedule (Result Http.Error Schedule)
    | ClickedEditCheckpoints
    | ClickedSaveCheckpoints
    | SelectedCheckpoint String
    | DeselectedCheckpoint String


update : Msg -> Model -> ( Model, Cmd Msg )
update msg model =
    case msg of
        ClickedRetry ->
            ( { model | status = LoadingSchedule }, getSchedule model.config.displayUrl GotSchedule )

        GotSchedule (Ok schedule) ->
            ( { model | status = DisplaySchedule schedule }, Cmd.none )

        GotSchedule (Err error) ->
            ( { model | status = Failure (errorToString error) }, Cmd.none )

        GotPossibleSchedule (Ok { checkpoints, start, finish }) ->
            let
                selected =
                    setFromCheckpointList checkpoints

                possibleSchedule =
                    PossibleSchedule checkpoints selected start finish
            in
            ( { model | status = EditCheckpoints possibleSchedule }, Cmd.none )

        GotPossibleSchedule (Err error) ->
            ( { model | status = Failure (errorToString error) }, Cmd.none )

        ClickedEditCheckpoints ->
            case model.status of
                DisplaySchedule schedule ->
                    let
                        url =
                            model.config.editUrl

                        cmd =
                            getSchedule url GotPossibleSchedule
                    in
                    ( { model | status = LoadingPossibleSchedule schedule }, cmd )

                _ ->
                    ( model, Cmd.none )

        ClickedSaveCheckpoints ->
            case model.status of
                EditCheckpoints { checkpoints, selected, start, finish } ->
                    let
                        url =
                            model.config.editUrl

                        csrfToken =
                            model.config.csrfToken

                        cmd =
                            postCheckpoints url csrfToken selected

                        selected_checkpoints =
                            List.filter (isSelected selected) checkpoints

                        schedule =
                            Schedule selected_checkpoints start finish
                    in
                    ( { model | status = SavingCheckpoints schedule }, cmd )

                _ ->
                    ( model, Cmd.none )

        SelectedCheckpoint fieldValue ->
            case model.status of
                EditCheckpoints ({ checkpoints, selected, start, finish } as possibleSchedule) ->
                    let
                        updatedSet =
                            Set.insert fieldValue selected

                        updatedSchedule =
                            { possibleSchedule | selected = updatedSet }
                    in
                    ( { model | status = EditCheckpoints updatedSchedule }, Cmd.none )

                _ ->
                    ( model, Cmd.none )

        DeselectedCheckpoint fieldValue ->
            case model.status of
                EditCheckpoints ({ checkpoints, selected, start, finish } as possibleSchedule) ->
                    let
                        updatedSet =
                            Set.remove fieldValue selected

                        updatedSchedule =
                            { possibleSchedule | selected = updatedSet }
                    in
                    ( { model | status = EditCheckpoints updatedSchedule }, Cmd.none )

                _ ->
                    ( model, Cmd.none )


setFromCheckpointList : List CheckpointPlace -> Set FieldValue
setFromCheckpointList checkpoints =
    List.filter .saved checkpoints
        |> List.map .fieldValue
        |> Set.fromList


isSelected : Set FieldValue -> CheckpointPlace -> Bool
isSelected selected checkpoint =
    Set.member checkpoint.fieldValue selected



-- VIEW


view : Model -> Html Msg
view model =
    let
        editButton =
            viewEditButton model.config.canEdit
    in
    div [ class "checkpoints mrgv-" ] <|
        case model.status of
            LoadingSchedule ->
                [ text "Loading route schedule..." ]

            DisplaySchedule schedule ->
                [ viewDisplaySchedule schedule
                , editButton ClickedEditCheckpoints
                ]

            LoadingPossibleSchedule schedule ->
                [ text "Loading additional checkpoints.. "
                , viewDisplaySchedule schedule
                ]

            EditCheckpoints possibleSchedule ->
                [ viewEditPossibleSchedule possibleSchedule
                , editButton ClickedSaveCheckpoints
                ]

            SavingCheckpoints schedule ->
                [ viewDisplaySchedule schedule ]

            Failure error ->
                [ text error
                , button
                    [ class "btn btn--secondary btn--block"
                    , onClick ClickedRetry
                    ]
                    [ text (messageToButtonText ClickedRetry) ]
                ]


viewDisplaySchedule : Schedule -> Html Msg
viewDisplaySchedule { checkpoints, start, finish } =
    div [ class "schedule" ]
        [ viewDisplayPlace Start start
        , viewDisplayCheckpoints checkpoints
        , viewDisplayPlace Finish finish
        ]


viewEditPossibleSchedule : PossibleSchedule -> Html Msg
viewEditPossibleSchedule { checkpoints, selected, start, finish } =
    div [ class "schedule" ]
        [ viewDisplayPlace Start start
        , viewEditCheckpoints checkpoints selected
        , viewDisplayPlace Finish finish
        ]


viewDisplayPlace : PlaceType -> Place -> Html Msg
viewDisplayPlace placeType place =
    div
        [ class "box box--tight box--default mrgv- pdg- place"
        , attribute "data-geom" "TODO"
        ]
        [ placeTypeToTitle placeType
        , viewPlaceInfo place
        ]


placeTypeToTitle : PlaceType -> Html Msg
placeTypeToTitle placeType =
    case placeType of
        Start ->
            h3 [ class "mrgv0" ] [ text "Start" ]

        Finish ->
            h3 [ class "mrgv0" ] [ text "Finish" ]

        Checkpoint ->
            text ""


viewPlaceInfo : Place -> Html Msg
viewPlaceInfo place =
    div [ class "grid grid--tight" ]
        [ viewPlaceName place.name place.altitude
        , viewPlaceSchedule place.schedule
        , viewPlaceType place.placeType
        , viewPlaceElevationAndDistance place.distance place.elevationGain place.elevationLoss
        ]


viewEditButton : Bool -> Msg -> Html Msg
viewEditButton canEdit message =
    if canEdit then
        button
            [ class "btn btn--primary btn--block"
            , onClick message
            ]
            [ text (messageToButtonText message) ]

    else
        text ""


messageToButtonText : Msg -> String
messageToButtonText message =
    case message of
        ClickedRetry ->
            "Retry"

        ClickedEditCheckpoints ->
            "Add/Remove Checkpoints"

        ClickedSaveCheckpoints ->
            "Save Checkpoints"

        _ ->
            ""


viewDisplayCheckpoints : List CheckpointPlace -> Html Msg
viewDisplayCheckpoints checkpoints =
    case checkpoints of
        [] ->
            div [ class "box box--default box--tight mrgv- pdg- place" ]
                [ text "No checkpoint has been added to this route. With checkpoints, you can track your progress during your run." ]

        _ ->
            List.map .place checkpoints
                |> List.map (viewDisplayPlace Checkpoint)
                |> ul [ class "list list--stacked" ]


viewEditCheckpoints : List CheckpointPlace -> Set FieldValue -> Html Msg
viewEditCheckpoints checkpoints selected =
    ul [ class "list list--stacked" ] <|
        List.map (viewEditCheckpoint selected) checkpoints


viewEditCheckpoint : Set FieldValue -> CheckpointPlace -> Html Msg
viewEditCheckpoint selected checkpoint =
    let
        isChecked =
            isSelected selected checkpoint

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
                        , td [] [ viewPlaceInfo checkpoint.place ]
                        ]
                    ]
                ]
            ]
        ]


viewCheckpointCheckbox : Msg -> Bool -> CheckpointPlace -> Html Msg
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


viewPlaceName : String -> Float -> Html Msg
viewPlaceName name altitude =
    div
        [ class "w-2/3 sm-w-4/5 grid__item place__name" ]
        [ text <| name ++ ", "
        , text <| format "0,0" altitude ++ "m"
        ]


viewPlaceSchedule : String -> Html Msg
viewPlaceSchedule schedule =
    div
        [ class "w-1/3 sm-w-1/5 grid__item text-right" ]
        [ text schedule ]


viewPlaceType : String -> Html Msg
viewPlaceType place_type =
    div
        [ class "w-1/2 grid__item text-small text-left" ]
        [ text place_type ]


viewPlaceElevationAndDistance : Float -> Float -> Float -> Html Msg
viewPlaceElevationAndDistance distance elevationGain elevationLoss =
    div
        [ class "w-1/2 grid__item text-small text-right" ]
        [ text <| format "0,0.0" distance ++ "km"
        , text <| " ➚ " ++ format "0,0" elevationGain ++ "m"
        , text <| " ➘ " ++ format "0,0" elevationLoss ++ "m"
        ]



-- HTTP


getSchedule : String -> (Result Error Schedule -> Msg) -> Cmd Msg
getSchedule url msg =
    Http.get
        { url = url
        , expect = Http.expectJson msg scheduleDecoder
        }


postCheckpoints : String -> String -> Set FieldValue -> Cmd Msg
postCheckpoints url csrftoken selected =
    let
        body =
            Http.stringPart "csrfmiddlewaretoken" csrftoken
                :: List.map (Http.stringPart "checkpoints") (Set.toList selected)
                |> Http.multipartBody
    in
    Http.post
        { url = url
        , body = body
        , expect = Http.expectJson GotSchedule scheduleDecoder
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
