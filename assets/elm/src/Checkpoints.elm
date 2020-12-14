port module Checkpoints exposing (main)

-- Display route checkpoints
--
-- TODO: adapt possible checkpoints distance from route
-- TODO: filter/select checkpoints by placeType
-- TODO: use webcomponents instead of ports for Leaflet

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
    | EditCheckpoints Schedule Selection
    | SavingCheckpoints Schedule


type alias Schedule =
    { checkpoints : List CheckpointPlace
    , start : Place
    , finish : Place
    }


scheduleDecoder : Decoder Schedule
scheduleDecoder =
    Decode.succeed Schedule
        |> required "checkpoints" (Decode.list checkpointDecoder)
        |> required "start" placeDecoder
        |> required "finish" placeDecoder


type alias Selection =
    Set FieldValue


selectionEncoder : Selection -> Value
selectionEncoder selection =
    Encode.set Encode.string selection


type alias CheckpointPlace =
    { place : Place
    , fieldValue : FieldValue
    , saved : Bool
    }


type alias FieldValue =
    String


checkpointDecoder : Decoder CheckpointPlace
checkpointDecoder =
    Decode.succeed CheckpointPlace
        |> custom placeDecoder
        |> required "field_value" Decode.string
        |> required "saved" Decode.bool


type PlaceClass
    = Start
    | Finish
    | Checkpoint
    | Possible


type alias Start =
    Place


type alias Finish =
    Place


type alias Place =
    { name : String
    , placeType : String
    , altitude : Float
    , schedule : String
    , distance : Float
    , elevationGain : Float
    , elevationLoss : Float
    , coords : Coords
    }


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
        |> required "coords" coordsDecoder


type alias Coords =
    { lat : Float, lng : Float }


coordsDecoder : Decoder Coords
coordsDecoder =
    Decode.succeed Coords
        |> required "lat" Decode.float
        |> required "lng" Decode.float



-- PORTS


type alias PlacesMsg =
    { action : String, places : List PlaceMarker }


type alias PlaceMarker =
    { id : String
    , placeClass : String
    , name : String
    , placeType : String
    , schedule : String
    , coords : Coords
    }


port updatePlaces : PlacesMsg -> Cmd msg


port clickedPlace : (String -> msg) -> Sub msg



-- UPDATE


type Msg
    = ClickedRetry
    | GotSchedule (Result Http.Error Schedule)
    | GotPossibleSchedule (Result Http.Error Schedule)
    | ClickedEditCheckpoints
    | ClickedSaveCheckpoints
    | ClickedCheckpoint String
    | ClickedSelectAll
    | ClickedClearAll


update : Msg -> Model -> ( Model, Cmd Msg )
update msg model =
    case msg of
        ClickedRetry ->
            ( { model | status = LoadingSchedule }, getSchedule model.config.displayUrl GotSchedule )

        GotSchedule result ->
            case result of
                Ok schedule ->
                    let
                        selection =
                            selectionFromCheckpointList schedule.checkpoints

                        placeMarkers =
                            placeMarkersFromSchedule schedule selection

                        updatePlacesCmd =
                            updatePlaces
                                { action = "display"
                                , places = placeMarkers
                                }
                    in
                    ( { model | status = DisplaySchedule schedule }, updatePlacesCmd )

                Err error ->
                    ( { model | status = Failure (errorToString error) }, Cmd.none )

        GotPossibleSchedule result ->
            case result of
                Ok schedule ->
                    let
                        selection =
                            List.filter .saved schedule.checkpoints
                                |> selectionFromCheckpointList

                        placeMarkers =
                            placeMarkersFromSchedule schedule selection

                        updatePlacesCmd =
                            updatePlaces { action = "edit", places = placeMarkers }
                    in
                    ( { model | status = EditCheckpoints schedule selection }, updatePlacesCmd )

                Err error ->
                    ( { model | status = Failure (errorToString error) }, Cmd.none )

        ClickedEditCheckpoints ->
            case model.status of
                DisplaySchedule schedule ->
                    let
                        url =
                            model.config.editUrl

                        getScheduleCmd =
                            getSchedule url GotPossibleSchedule
                    in
                    ( { model | status = LoadingPossibleSchedule schedule }, getScheduleCmd )

                _ ->
                    ( model, Cmd.none )

        ClickedSaveCheckpoints ->
            case model.status of
                EditCheckpoints { checkpoints, start, finish } selection ->
                    let
                        selected_checkpoints =
                            List.filter (isSelected selection) checkpoints

                        schedule =
                            Schedule selected_checkpoints start finish

                        postCheckpointsCmd =
                            postCheckpoints model.config.editUrl model.config.csrfToken selection
                    in
                    ( { model | status = SavingCheckpoints schedule }, postCheckpointsCmd )

                _ ->
                    ( model, Cmd.none )

        ClickedCheckpoint fieldValue ->
            let
                updateSelection : Schedule -> Selection -> Selection
                updateSelection _ selection =
                    if Set.member fieldValue selection then
                        Set.remove fieldValue selection

                    else
                        Set.insert fieldValue selection
            in
            updateModelSelection updateSelection model

        ClickedSelectAll ->
            let
                updateSelection : Schedule -> Selection -> Selection
                updateSelection schedule _ =
                    selectionFromCheckpointList schedule.checkpoints
            in
            updateModelSelection updateSelection model

        ClickedClearAll ->
            let
                updateSelection : Schedule -> Selection -> Selection
                updateSelection _ _ =
                    Set.empty
            in
            updateModelSelection updateSelection model


updateModelSelection : (Schedule -> Selection -> Selection) -> Model -> ( Model, Cmd Msg )
updateModelSelection updateSetFromPossibleSchedule model =
    case model.status of
        EditCheckpoints schedule selection ->
            let
                updatedSelection =
                    updateSetFromPossibleSchedule schedule selection

                placeMarkers =
                    placeMarkersFromSchedule schedule updatedSelection

                updatePlacesCmd =
                    updatePlaces { action = "edit", places = placeMarkers }
            in
            ( { model | status = EditCheckpoints schedule updatedSelection }, updatePlacesCmd )

        _ ->
            ( model, Cmd.none )


selectionFromCheckpointList : List CheckpointPlace -> Selection
selectionFromCheckpointList checkpoints =
    List.map .fieldValue checkpoints |> Set.fromList


isSelected : Selection -> CheckpointPlace -> Bool
isSelected selection checkpoint =
    Set.member checkpoint.fieldValue selection



-- Place markers for Leaflet


placeMarkersFromSchedule : Schedule -> Selection -> List PlaceMarker
placeMarkersFromSchedule { start, finish, checkpoints } selection =
    let
        areSelected =
            List.map (isSelected selection) checkpoints
    in
    List.map2 placeMarkerFromCheckpointPlace areSelected checkpoints
        |> (::) (placeMarkerFromPlace Start Nothing start)
        |> (::) (placeMarkerFromPlace Finish Nothing finish)


placeMarkerFromCheckpointPlace : Bool -> CheckpointPlace -> PlaceMarker
placeMarkerFromCheckpointPlace selection checkpoint =
    let
        class =
            if selection then
                Checkpoint

            else
                Possible
    in
    placeMarkerFromPlace class (Just checkpoint.fieldValue) checkpoint.place


placeMarkerFromPlace : PlaceClass -> Maybe FieldValue -> Place -> PlaceMarker
placeMarkerFromPlace placeClass maybeFieldValue place =
    let
        class =
            case placeClass of
                Start ->
                    "start"

                Finish ->
                    "finish"

                Checkpoint ->
                    "checkpoint"

                Possible ->
                    "possible"

        id =
            case maybeFieldValue of
                Just fieldValue ->
                    fieldValue

                Nothing ->
                    ""
    in
    PlaceMarker
        id
        class
        (placeNameText place.name place.altitude)
        place.placeType
        place.schedule
        place.coords



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
                [ viewDisplaySchedule schedule
                , viewLoadingButton "Loading additional checkpoints..."
                ]

            EditCheckpoints schedule selection ->
                [ viewEditSchedule schedule selection
                , editButton ClickedSaveCheckpoints
                ]

            SavingCheckpoints schedule ->
                [ viewDisplaySchedule schedule
                , viewLoadingButton "Saving checkpoints..."
                ]

            Failure error ->
                [ text error
                , button
                    [ class "btn btn--secondary btn--block"
                    , onClick ClickedRetry
                    ]
                    [ text (messageToButtonText ClickedRetry) ]
                ]



-- Schedule


viewDisplaySchedule : Schedule -> Html Msg
viewDisplaySchedule { start, checkpoints, finish } =
    let
        displayCheckpoints =
            viewDisplayCheckpoints checkpoints
    in
    viewSchedule displayCheckpoints start finish


viewEditSchedule : Schedule -> Selection -> Html Msg
viewEditSchedule { start, checkpoints, finish } selection =
    let
        displayCheckpoints =
            viewEditCheckpoints checkpoints selection
    in
    viewSchedule displayCheckpoints start finish


viewSchedule : Html Msg -> Start -> Finish -> Html Msg
viewSchedule displayCheckpoints start finish =
    div [ class "schedule" ]
        [ viewDisplayPlace Start start
        , displayCheckpoints
        , viewDisplayPlace Finish finish
        ]



--  Checkpoints


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


viewEditCheckpoints : List CheckpointPlace -> Selection -> Html Msg
viewEditCheckpoints checkpoints selection =
    case checkpoints of
        [] ->
            div [ class "box box--default box--tight mrgv- pdg- place" ]
                [ text "Sorry, but no checkpoint was found to this route. " ]

        _ ->
            div []
                [ button [ onClick ClickedSelectAll ] [ text (messageToButtonText ClickedSelectAll) ]
                , button [ onClick ClickedClearAll ] [ text (messageToButtonText ClickedClearAll) ]
                , ul [ class "list list--stacked" ] <|
                    List.map (viewEditCheckpoint selection) checkpoints
                ]


viewEditCheckpoint : Selection -> CheckpointPlace -> Html Msg
viewEditCheckpoint selection checkpoint =
    let
        isChecked =
            isSelected selection checkpoint
    in
    li
        [ class "box box--tight mrgv- place"
        , classList [ ( "box--default", isChecked ) ]
        ]
        [ label [ for checkpoint.fieldValue, class "label pdg0" ]
            [ table [ class "mrgv0 pdg0" ]
                [ tbody []
                    [ tr []
                        [ td [ class "text-center", width 10 ] [ viewCheckpointCheckbox isChecked checkpoint ]
                        , td [] [ viewPlaceInfo checkpoint.place ]
                        ]
                    ]
                ]
            ]
        ]


viewCheckpointCheckbox : Bool -> CheckpointPlace -> Html Msg
viewCheckpointCheckbox isChecked checkpoint =
    input
        [ id checkpoint.fieldValue
        , type_ "checkbox"
        , class "checkbox"
        , value checkpoint.fieldValue
        , checked isChecked
        , onClick (ClickedCheckpoint checkpoint.fieldValue)
        ]
        []



-- Places


viewDisplayPlace : PlaceClass -> Place -> Html Msg
viewDisplayPlace placeClass place =
    div
        [ class "box box--tight box--default mrgv- pdg- place" ]
        [ placeClassToTitle placeClass
        , viewPlaceInfo place
        ]


placeClassToTitle : PlaceClass -> Html Msg
placeClassToTitle placeType =
    case placeType of
        Start ->
            h3 [ class "mrgv0" ] [ text "Start" ]

        Finish ->
            h3 [ class "mrgv0" ] [ text "Finish" ]

        Checkpoint ->
            text ""

        Possible ->
            text ""


viewPlaceInfo : Place -> Html Msg
viewPlaceInfo place =
    div [ class "grid grid--tight" ]
        [ viewPlaceName place.name place.altitude
        , viewPlaceSchedule place.schedule
        , viewPlaceType place.placeType
        , viewPlaceElevationAndDistance place.distance place.elevationGain place.elevationLoss
        ]


viewPlaceName : String -> Float -> Html Msg
viewPlaceName name altitude =
    div
        [ class "w-2/3 sm-w-4/5 grid__item place__name" ]
        [ text (placeNameText name altitude)
        ]


placeNameText : String -> Float -> String
placeNameText name altitude =
    name ++ ", " ++ format "0,0" altitude ++ "m"


viewPlaceSchedule : String -> Html Msg
viewPlaceSchedule schedule =
    div
        [ class "w-1/3 sm-w-1/5 grid__item text-right" ]
        [ text schedule ]


viewPlaceType : String -> Html Msg
viewPlaceType placeType =
    div
        [ class "w-1/2 grid__item text-small text-left" ]
        [ text placeType ]


viewPlaceElevationAndDistance : Float -> Float -> Float -> Html Msg
viewPlaceElevationAndDistance distance elevationGain elevationLoss =
    div
        [ class "w-1/2 grid__item text-small text-right" ]
        [ text <| format "0,0.0" distance ++ "km"
        , text <| " ➚ " ++ format "0,0" elevationGain ++ "m"
        , text <| " ➘ " ++ format "0,0" elevationLoss ++ "m"
        ]



-- Button


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


viewLoadingButton : String -> Html Msg
viewLoadingButton labelText =
    button
        [ class "btn btn--primary btn--block btn--disabled"
        ]
        [ div [ class "inline-flex align-items-center" ]
            [ div [ class "loader" ] []
            , div [ class "pdgl--" ] [ text labelText ]
            ]
        ]


messageToButtonText : Msg -> String
messageToButtonText message =
    case message of
        ClickedRetry ->
            "Retry"

        ClickedEditCheckpoints ->
            "Add/Remove Checkpoints"

        ClickedSaveCheckpoints ->
            "Save Checkpoints"

        ClickedSelectAll ->
            "Select All"

        ClickedClearAll ->
            "Clear All"

        _ ->
            ""



-- HTTP


getSchedule : String -> (Result Error Schedule -> Msg) -> Cmd Msg
getSchedule url msg =
    Http.get
        { url = url
        , expect = Http.expectJson msg scheduleDecoder
        }


postCheckpoints : String -> String -> Selection -> Cmd Msg
postCheckpoints url csrfToken selection =
    let
        body =
            Encode.object [ ( "checkpoints", selectionEncoder selection ) ]
    in
    Http.request
        { method = "POST"
        , headers = [ Http.header "X-CSRFToken" csrfToken ]
        , url = url
        , body = Http.jsonBody body
        , expect = Http.expectJson GotSchedule scheduleDecoder
        , timeout = Nothing
        , tracker = Nothing
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
