port module Checkpoints exposing (main)

-- Display route checkpoints
--
-- TODO: adapt possible checkpoints distance from route
-- TODO: filter/select checkpoints by placeType
-- TODO: use webcomponents instead of ports for Leaflet

import Browser
import Html exposing (..)
import Html.Attributes exposing (checked, class, classList, for, id, name, selected, type_, value, width)
import Html.Events exposing (onClick, onInput)
import Http exposing (Error)
import Json.Decode as Decode exposing (Decoder)
import Json.Decode.Pipeline exposing (custom, required)
import Json.Encode as Encode exposing (Value)
import Numeral exposing (format)
import SelectList exposing (Position(..), SelectList)
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
            getSchedule url

        model =
            { config = config, status = initialStatus }
    in
    ( model, cmd )



-- MODEL


type alias Model =
    { config : Config
    , status : Status
    }


type alias Config =
    { displayUrl : String
    , checkpointUrl : String
    , startUrl : String
    , finishUrl : String
    , csrfToken : String
    , canEdit : Bool
    }


type alias Status =
    { checkpoints : CheckpointStatus
    , start : PlaceStatus
    , finish : PlaceStatus
    }


type CheckpointStatus
    = LoadingCheckpoints (List Checkpoint)
    | DisplayCheckpoints (List Checkpoint)
    | EditingCheckpoints (List Checkpoint) CheckpointSelection
    | SavingCheckpoints (List Checkpoint)
    | ErrorCheckpoints String


type PlaceStatus
    = LoadingPlace (Maybe Place)
    | DisplayPlace Place
    | EditingPlace (SelectList Place)
    | SavingPlace Place
    | ErrorPlace String


type alias CheckpointSelection =
    Set PlaceId


type Place
    = Start PlaceInfo
    | Finish PlaceInfo


type Checkpoint
    = Checkpoint PlaceInfo


type alias PlaceInfo =
    { name : String
    , placeType : String
    , altitude : Float
    , schedule : String
    , distance : Float
    , elevationGain : Float
    , elevationLoss : Float
    , coords : Coords
    , placeId : PlaceId
    }


type alias PlaceId =
    String


type alias Coords =
    { lat : Float, lng : Float }



-- PORTS


type alias PlacesMsg =
    { places : List PlaceMarker }


type alias PlaceMarker =
    { id : String
    , placeClass : String
    , name : String
    , placeType : String
    , schedule : String
    , coords : Coords
    , selected : Bool
    , edit : Bool
    }


subscriptions : Model -> Sub Msg
subscriptions model =
    clickedPlace (clickedPlaceMessage model)


clickedPlaceMessage : Model -> { placeId : PlaceId, placeClass : String } -> Msg
clickedPlaceMessage model { placeId, placeClass } =
    case placeClass of
        "start" ->
            case model.status.start of
                EditingPlace placeList ->
                    PickedPlace placeList placeId

                _ ->
                    Noop

        "finish" ->
            case model.status.finish of
                EditingPlace placeList ->
                    PickedPlace placeList placeId

                _ ->
                    Noop

        "checkpoint" ->
            case model.status.checkpoints of
                EditingCheckpoints _ _ ->
                    ClickedCheckpoint placeId

                _ ->
                    Noop

        _ ->
            Noop


port updatePlaces : PlacesMsg -> Cmd msg


port clickedPlace : ({ placeId : String, placeClass : String } -> msg) -> Sub msg



-- UPDATE


type Msg
    = Noop
      -- Initialize
    | ClickedRetry
    | GotSchedule (Result Http.Error ScheduleData)
      -- Checkpoints
    | ClickedEditCheckpoints
    | GotPossibleCheckpoints (Result Http.Error ( List Checkpoint, CheckpointSelection ))
    | ClickedCheckpoint String
    | ClickedSelectAllCheckpoints
    | ClickedClearAllCheckpoints
    | ClickedSaveCheckpoints
    | GotCheckpoints (Result Http.Error (List Checkpoint))
      -- Start and Finish
    | ClickedEditPlace Place
    | GotPossiblePlace Place (Result Http.Error (SelectList Place))
    | PickedPlace (SelectList Place) String
    | ClickedSavePlace (SelectList Place)
    | GotPlace Place (Result Http.Error Place)


initialStatus =
    { checkpoints = LoadingCheckpoints []
    , start = LoadingPlace Nothing
    , finish = LoadingPlace Nothing
    }


update : Msg -> Model -> ( Model, Cmd Msg )
update msg ({ config, status } as model) =
    case msg of
        Noop ->
            ( model, Cmd.none )

        ClickedRetry ->
            ( { model | status = initialStatus }, getSchedule model.config.displayUrl )

        GotSchedule (Ok scheduleData) ->
            let
                updatedStatus =
                    { checkpoints = DisplayCheckpoints scheduleData.checkpointData
                    , start = DisplayPlace scheduleData.startData
                    , finish = DisplayPlace scheduleData.finishData
                    }

                placeMarkers =
                    placeMarkersFromStatus updatedStatus

                updatePlacesCmd =
                    updatePlaces { places = placeMarkers }
            in
            ( { model | status = updatedStatus }, updatePlacesCmd )

        GotSchedule (Err error) ->
            let
                updatedStatus =
                    { checkpoints = ErrorCheckpoints <| errorToString error
                    , start = ErrorPlace <| errorToString error
                    , finish = ErrorPlace <| errorToString error
                    }
            in
            ( { model | status = updatedStatus }, Cmd.none )

        ClickedEditCheckpoints ->
            case status.checkpoints of
                DisplayCheckpoints checkpoints ->
                    let
                        updatedCheckpoints =
                            LoadingCheckpoints checkpoints

                        updatedStatus =
                            { status | checkpoints = updatedCheckpoints }
                    in
                    ( { model | status = updatedStatus }
                    , getCheckpoints model.config.checkpointUrl
                    )

                _ ->
                    ( model, Cmd.none )

        GotPossibleCheckpoints (Ok ( checkpoints, selection )) ->
            let
                updatedStatus =
                    { status | checkpoints = EditingCheckpoints checkpoints selection }

                placeMarkers =
                    placeMarkersFromStatus updatedStatus
            in
            ( { model | status = updatedStatus }, updatePlaces <| PlacesMsg placeMarkers )

        GotPossibleCheckpoints (Err error) ->
            let
                updatedStatus =
                    { status | checkpoints = ErrorCheckpoints <| errorToString error }
            in
            ( { model | status = updatedStatus }, Cmd.none )

        ClickedCheckpoint placeId ->
            let
                updateSelectionFunction : List Checkpoint -> CheckpointSelection -> CheckpointSelection
                updateSelectionFunction _ selection =
                    if Set.member placeId selection then
                        Set.remove placeId selection

                    else
                        Set.insert placeId selection
            in
            updateCheckpointSelection updateSelectionFunction model

        ClickedSelectAllCheckpoints ->
            let
                updateSelectionFunction : List Checkpoint -> CheckpointSelection -> CheckpointSelection
                updateSelectionFunction checkpoints _ =
                    List.map placeInfoFromCheckpoint checkpoints
                        |> List.map .placeId
                        |> Set.fromList
            in
            updateCheckpointSelection updateSelectionFunction model

        ClickedClearAllCheckpoints ->
            let
                updateSelectionFunction : List Checkpoint -> CheckpointSelection -> CheckpointSelection
                updateSelectionFunction _ _ =
                    Set.empty
            in
            updateCheckpointSelection updateSelectionFunction model

        ClickedSaveCheckpoints ->
            case status.checkpoints of
                EditingCheckpoints checkpoints selection ->
                    let
                        updatedCheckpoints =
                            checkpoints
                                |> List.filter (isSelected selection)

                        updatedStatus =
                            { status | checkpoints = SavingCheckpoints updatedCheckpoints }

                        postCmd =
                            postCheckpoints config.checkpointUrl config.csrfToken selection
                    in
                    ( { model | status = updatedStatus }
                    , postCmd
                    )

                _ ->
                    ( model, Cmd.none )

        GotCheckpoints (Ok checkpoints) ->
            let
                updatedStatus =
                    { status | checkpoints = DisplayCheckpoints checkpoints }

                placeMarkers =
                    placeMarkersFromStatus updatedStatus
            in
            ( { model | status = updatedStatus }, updatePlaces <| PlacesMsg placeMarkers )

        GotCheckpoints (Err error) ->
            let
                updatedStatus =
                    { status | checkpoints = ErrorCheckpoints <| errorToString error }
            in
            ( { model | status = updatedStatus }, Cmd.none )

        ClickedEditPlace place ->
            let
                ( updatedStatus, url ) =
                    case place of
                        Start _ ->
                            ( { status | start = LoadingPlace (Just place) }
                            , model.config.startUrl
                            )

                        Finish _ ->
                            ( { status | finish = LoadingPlace (Just place) }
                            , model.config.finishUrl
                            )
            in
            ( { model | status = updatedStatus }, getPlace place url )

        GotPossiblePlace place (Ok placeList) ->
            let
                updatedStatus =
                    case place of
                        Start _ ->
                            { status | start = EditingPlace placeList }

                        Finish _ ->
                            { status | finish = EditingPlace placeList }

                placeMarkers =
                    placeMarkersFromStatus updatedStatus
            in
            ( { model | status = updatedStatus }, updatePlaces <| PlacesMsg placeMarkers )

        GotPossiblePlace place (Err error) ->
            let
                updatedStatus =
                    case place of
                        Start _ ->
                            { status | start = ErrorPlace <| errorToString error }

                        Finish _ ->
                            { status | finish = ErrorPlace <| errorToString error }
            in
            ( { model | status = updatedStatus }, Cmd.none )

        PickedPlace placeList index ->
            let
                oldIndex =
                    SelectList.index placeList

                newIndex =
                    Maybe.withDefault oldIndex (String.toInt index)

                updatedPlaceList =
                    SelectList.selectedMap (\_ list -> list) placeList
                        |> List.drop newIndex
                        |> List.head
                        |> Maybe.withDefault placeList

                updatedStatus =
                    case SelectList.selected placeList of
                        Start _ ->
                            { status | start = EditingPlace updatedPlaceList }

                        Finish _ ->
                            { status | finish = EditingPlace updatedPlaceList }

                placeMarkers =
                    placeMarkersFromStatus updatedStatus
            in
            ( { model | status = updatedStatus }, updatePlaces <| PlacesMsg placeMarkers )

        ClickedSavePlace placeList ->
            let
                place =
                    SelectList.selected placeList

                placeId =
                    place |> placeInfoFromPlace |> .placeId

                ( updatedStatus, url ) =
                    case place of
                        Start _ ->
                            ( { status | start = SavingPlace place }, model.config.startUrl )

                        Finish _ ->
                            ( { status | finish = SavingPlace place }, model.config.finishUrl )
            in
            ( { model | status = updatedStatus }
            , postPlace place url model.config.csrfToken placeId
            )

        GotPlace _ (Ok place) ->
            let
                updatedStatus =
                    case place of
                        Start _ ->
                            { status | start = DisplayPlace place }

                        Finish _ ->
                            { status | finish = DisplayPlace place }

                placeMarkers =
                    placeMarkersFromStatus updatedStatus
            in
            ( { model | status = updatedStatus }, updatePlaces <| PlacesMsg placeMarkers )

        GotPlace place (Err error) ->
            let
                updatedStatus =
                    case place of
                        Start _ ->
                            { status | start = ErrorPlace <| errorToString error }

                        Finish _ ->
                            { status | start = ErrorPlace <| errorToString error }
            in
            ( { model | status = updatedStatus }, Cmd.none )


updateCheckpointSelection : (List Checkpoint -> CheckpointSelection -> CheckpointSelection) -> Model -> ( Model, Cmd Msg )
updateCheckpointSelection updateSelectionFunction model =
    case model.status.checkpoints of
        EditingCheckpoints checkpoints selection ->
            let
                status =
                    model.status

                updatedSelection =
                    updateSelectionFunction checkpoints selection

                updatedStatus =
                    { status | checkpoints = EditingCheckpoints checkpoints updatedSelection }

                placeMarkers =
                    placeMarkersFromStatus updatedStatus

                updatePlacesCmd =
                    updatePlaces <| PlacesMsg placeMarkers
            in
            ( { model | status = updatedStatus }, updatePlacesCmd )

        _ ->
            ( model, Cmd.none )


isSelected : CheckpointSelection -> Checkpoint -> Bool
isSelected selection (Checkpoint checkpointInfo) =
    Set.member checkpointInfo.placeId selection


placeInfoFromCheckpoint : Checkpoint -> PlaceInfo
placeInfoFromCheckpoint (Checkpoint placeInfo) =
    placeInfo


placeInfoFromPlace : Place -> PlaceInfo
placeInfoFromPlace place =
    case place of
        Start placeInfo ->
            placeInfo

        Finish placeInfo ->
            placeInfo



-- PLACE MARKERS FOR LEAFLET


placeMarkersFromStatus : Status -> List PlaceMarker
placeMarkersFromStatus { checkpoints, start, finish } =
    placeMarkersFromCheckpoints checkpoints
        ++ placeMarkersFromPlace start
        ++ placeMarkersFromPlace finish



--


placeMarkersFromCheckpoints : CheckpointStatus -> List PlaceMarker
placeMarkersFromCheckpoints checkpointStatus =
    case checkpointStatus of
        EditingCheckpoints checkpoints selection ->
            let
                areSelected =
                    List.map (isSelected selection) checkpoints
            in
            List.map2 (placeMarkerFromCheckpoint True) areSelected checkpoints

        DisplayCheckpoints checkpoints ->
            List.map (placeMarkerFromCheckpoint False True) checkpoints

        _ ->
            []


placeMarkerFromCheckpoint : Bool -> Bool -> Checkpoint -> PlaceMarker
placeMarkerFromCheckpoint edit selected (Checkpoint checkpointInfo) =
    placeMarkerFromPlaceInfo "checkpoint" selected edit checkpointInfo.placeId checkpointInfo



-- Place


placeMarkersFromPlace : PlaceStatus -> List PlaceMarker
placeMarkersFromPlace placeStatus =
    case placeStatus of
        EditingPlace selectList ->
            SelectList.selectedMap placeMarkerFromSelectedMap selectList

        DisplayPlace place ->
            [ placeMarkerFromPlace place ]

        LoadingPlace maybePlace ->
            case maybePlace of
                Just place ->
                    [ placeMarkerFromPlace place ]

                Nothing ->
                    []

        SavingPlace place ->
            [ placeMarkerFromPlace place ]

        ErrorPlace _ ->
            []


placeMarkerFromSelectedMap : Position -> SelectList Place -> PlaceMarker
placeMarkerFromSelectedMap position selectList =
    let
        place =
            SelectList.selected selectList

        selected =
            position == Selected

        index =
            SelectList.index selectList
    in
    case place of
        Start info ->
            placeMarkerFromPlaceInfo "start" selected True (String.fromInt index) info

        Finish info ->
            placeMarkerFromPlaceInfo "finish" selected True (String.fromInt index) info


placeMarkerFromPlace : Place -> PlaceMarker
placeMarkerFromPlace place =
    case place of
        Start info ->
            placeMarkerFromPlaceInfo "start" True False info.placeId info

        Finish info ->
            placeMarkerFromPlaceInfo "finish" True False info.placeId info


placeMarkerFromPlaceInfo : String -> Bool -> Bool -> PlaceId -> PlaceInfo -> PlaceMarker
placeMarkerFromPlaceInfo placeClass selected edit placeId placeInfo =
    PlaceMarker
        placeId
        placeClass
        (placeNameText placeInfo.name placeInfo.altitude)
        placeInfo.placeType
        placeInfo.schedule
        placeInfo.coords
        selected
        edit



-- VIEW


view : Model -> Html Msg
view model =
    let
        { config, status } =
            model
    in
    div [ class "checkpoints mrgv-" ] <|
        [ div [ class "schedule" ]
            [ viewPlace config.canEdit status.start
            , viewCheckpoints status.checkpoints
            , viewPlace config.canEdit status.finish
            , viewCheckpointEditButton config.canEdit status.checkpoints
            ]
        ]



--  Checkpoints


viewCheckpoints : CheckpointStatus -> Html Msg
viewCheckpoints status =
    case status of
        EditingCheckpoints checkpoints selection ->
            viewEditCheckpoints checkpoints selection

        DisplayCheckpoints checkpoints ->
            viewDisplayCheckpoints checkpoints

        LoadingCheckpoints checkpoints ->
            case checkpoints of
                [] ->
                    div [ class "box" ] [ div [ class "loader pull-left mrgr--" ] [], text "Loading checkpoints.." ]

                _ ->
                    viewDisplayCheckpoints checkpoints

        SavingCheckpoints checkpoints ->
            viewDisplayCheckpoints checkpoints

        ErrorCheckpoints error ->
            text error


viewDisplayCheckpoints : List Checkpoint -> Html Msg
viewDisplayCheckpoints checkpoints =
    case checkpoints of
        [] ->
            div [ class "box box--default box--tight mrgv- pdg- place" ]
                [ text "No checkpoint has been added to this route. With checkpoints, you can track your progress during your run." ]

        _ ->
            List.map placeInfoFromCheckpoint checkpoints
                |> List.map viewDisplayCheckpoint
                |> ul [ class "list list--stacked" ]


viewDisplayCheckpoint : PlaceInfo -> Html Msg
viewDisplayCheckpoint checkpointInfo =
    div [ class "box box--tight box--default mrgv- pdg- place" ]
        [ viewCheckpointInfo checkpointInfo ]


viewEditCheckpoints : List Checkpoint -> CheckpointSelection -> Html Msg
viewEditCheckpoints checkpoints selection =
    case checkpoints of
        [] ->
            div [ class "box box--default box--tight mrgv- pdg- place" ]
                [ text "Sorry, no checkpoint was found for this route. " ]

        _ ->
            div []
                [ viewClearSelectAllButtons
                , List.map placeInfoFromCheckpoint checkpoints
                    |> List.map (viewEditCheckpoint selection)
                    |> ul [ class "list list--stacked" ]
                ]


viewEditCheckpoint : CheckpointSelection -> PlaceInfo -> Html Msg
viewEditCheckpoint selection checkpointInfo =
    let
        isChecked =
            Set.member checkpointInfo.placeId selection
    in
    li
        [ class "box box--tight mrgv- place"
        , classList [ ( "box--default", isChecked ) ]
        ]
        [ label [ for checkpointInfo.placeId, class "label pdg0" ]
            [ table [ class "mrgv0 pdg0" ]
                [ tbody []
                    [ tr []
                        [ td [ class "text-center", width 10 ] [ viewCheckpointCheckbox isChecked checkpointInfo ]
                        , td [] [ viewCheckpointInfo checkpointInfo ]
                        ]
                    ]
                ]
            ]
        ]


viewCheckpointCheckbox : Bool -> PlaceInfo -> Html Msg
viewCheckpointCheckbox isChecked checkpointInfo =
    input
        [ id checkpointInfo.placeId
        , type_ "checkbox"
        , class "checkbox"
        , value checkpointInfo.placeId
        , checked isChecked
        , onClick (ClickedCheckpoint checkpointInfo.placeId)
        ]
        []


viewCheckpointInfo : PlaceInfo -> Html Msg
viewCheckpointInfo placeInfo =
    div [ class "grid grid--tight" ]
        [ viewCheckpointPlaceName placeInfo.name placeInfo.altitude
        , viewPlaceSchedule placeInfo.schedule
        , viewPlaceType placeInfo.placeType
        , viewPlaceElevationAndDistance placeInfo.distance placeInfo.elevationGain placeInfo.elevationLoss
        ]


viewCheckpointPlaceName : String -> Float -> Html Msg
viewCheckpointPlaceName name altitude =
    div
        [ class "w-2/3 sm-w-4/5 grid__item place__name" ]
        [ text (placeNameText name altitude)
        ]



-- Places


viewPlace : Bool -> PlaceStatus -> Html Msg
viewPlace canEdit placeStatus =
    let
        button =
            viewPlaceEditButton canEdit placeStatus
    in
    case placeStatus of
        EditingPlace placeList ->
            viewEditPlace button placeList

        LoadingPlace maybePlace ->
            case maybePlace of
                Just place ->
                    viewDisplayPlace button place

                Nothing ->
                    div [ class "box" ] [ div [ class "loader pull-left mrgr--" ] [], text "Loading place.." ]

        DisplayPlace place ->
            viewDisplayPlace button place

        SavingPlace place ->
            viewDisplayPlace button place

        ErrorPlace error ->
            text error


viewDisplayPlace : Html Msg -> Place -> Html Msg
viewDisplayPlace button place =
    let
        placeInfo =
            placeInfoFromPlace place
    in
    div
        [ class "box box--tight box--default mrgv- pdg- place" ]
        [ h3 [ class "mrgv0" ] [ text <| titleFromPlace place ]
        , div [ class "grid grid--tight" ]
            [ viewDisplayPlaceName button place
            , viewPlaceSchedule placeInfo.schedule
            , viewPlaceType placeInfo.placeType
            , viewPlaceElevationAndDistance placeInfo.distance placeInfo.elevationGain placeInfo.elevationLoss
            ]
        ]


viewDisplayPlaceName : Html Msg -> Place -> Html Msg
viewDisplayPlaceName button place =
    let
        placeInfo =
            placeInfoFromPlace place
    in
    div
        [ class "w-2/3 sm-w-4/5 grid__item place__name" ]
        [ text (placeNameText placeInfo.name placeInfo.altitude)
        , span [ class "pdgl" ] [ button ]
        ]


viewEditPlace : Html Msg -> SelectList Place -> Html Msg
viewEditPlace button placeList =
    let
        place =
            SelectList.selected placeList

        placeInfo =
            placeInfoFromPlace place
    in
    div
        [ class "box box--tight box--default mrgv- pdg- place" ]
        [ h3 [ class "mrgv0" ] [ text <| titleFromPlace place ]
        , div [ class "grid grid--tight" ]
            [ viewEditPlaceName button placeList
            , viewPlaceSchedule placeInfo.schedule
            , viewPlaceType placeInfo.placeType
            , viewPlaceElevationAndDistance placeInfo.distance placeInfo.elevationGain placeInfo.elevationLoss
            ]
        ]


viewEditPlaceName : Html Msg -> SelectList Place -> Html Msg
viewEditPlaceName button placeList =
    div
        [ class "w-2/3 sm-w-4/5 grid__item" ]
        [ div [ class "media media--small" ]
            [ div [ class "media__body" ]
                [ select
                    [ class "field field--small", onInput (PickedPlace placeList) ]
                    (SelectList.selectedMap selectOption placeList)
                ]
            , div [ class "media__right" ]
                [ button
                ]
            ]
        ]


selectOption : SelectList.Position -> SelectList Place -> Html Msg
selectOption position placeList =
    let
        index =
            SelectList.index placeList |> String.fromInt

        isChecked =
            position == Selected

        placeInfo =
            SelectList.selected placeList |> placeInfoFromPlace
    in
    option
        [ value index, selected isChecked ]
        [ text (placeNameText placeInfo.name placeInfo.altitude) ]


titleFromPlace : Place -> String
titleFromPlace place =
    case place of
        Start _ ->
            "Start"

        Finish _ ->
            "Finish"



-- PlaceInfo


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



-- Buttons


viewPlaceEditButton : Bool -> PlaceStatus -> Html Msg
viewPlaceEditButton canEdit placeStatus =
    if canEdit then
        case placeStatus of
            DisplayPlace place ->
                button [ class "btn btn--secondary btn--small", onClick (ClickedEditPlace place) ]
                    [ text "Edit" ]

            LoadingPlace _ ->
                div [ class "loader" ] []

            EditingPlace placeList ->
                button [ class "btn btn--primary btn--small", onClick (ClickedSavePlace placeList) ]
                    [ text "Save" ]

            SavingPlace _ ->
                div [ class "loader" ] []

            ErrorPlace _ ->
                text ""

    else
        text ""


viewCheckpointEditButton : Bool -> CheckpointStatus -> Html Msg
viewCheckpointEditButton canEdit status =
    if canEdit then
        case status of
            DisplayCheckpoints _ ->
                a
                    [ class "btn btn--primary btn--block"
                    , onClick ClickedEditCheckpoints
                    ]
                    [ text (messageToButtonText ClickedEditCheckpoints) ]

            LoadingCheckpoints _ ->
                a
                    [ class "btn btn--primary btn--block btn--disabled"
                    ]
                    [ div [ class "inline-flex align-items-center" ]
                        [ div [ class "loader" ] []
                        , div [ class "pdgl--" ] [ text "Loading Checkpoints..." ]
                        ]
                    ]

            EditingCheckpoints _ _ ->
                a
                    [ class "btn btn--primary btn--block"
                    , onClick ClickedSaveCheckpoints
                    ]
                    [ text (messageToButtonText ClickedSaveCheckpoints) ]

            SavingCheckpoints _ ->
                a
                    [ class "btn btn--primary btn--block btn--disabled"
                    ]
                    [ div [ class "inline-flex align-items-center" ]
                        [ div [ class "loader" ] []
                        , div [ class "pdgl--" ] [ text "Saving Checkpoints..." ]
                        ]
                    ]

            ErrorCheckpoints _ ->
                text ""

    else
        text ""


viewClearSelectAllButtons : Html Msg
viewClearSelectAllButtons =
    div []
        [ h4 [] [ text "Edit Checkpoints" ]
        , div [ class "mrgv-" ]
            [ button
                [ class "btn btn--primary btn--block btn--small"
                , onClick ClickedSaveCheckpoints
                ]
                [ text "Save Checkpoints" ]
            ]
        , div [ class "grid grid--small" ]
            [ div [ class "grid__item w-1/2" ]
                [ button
                    [ onClick ClickedSelectAllCheckpoints
                    , class "btn btn--secondary btn--block btn--small "
                    ]
                    [ text (messageToButtonText ClickedSelectAllCheckpoints) ]
                ]
            , div [ class "grid__item w-1/2" ]
                [ button
                    [ onClick ClickedClearAllCheckpoints
                    , class "btn btn--secondary btn--block btn--small "
                    ]
                    [ text (messageToButtonText ClickedClearAllCheckpoints) ]
                ]
            ]
        ]


messageToButtonText : Msg -> String
messageToButtonText message =
    case message of
        ClickedRetry ->
            "Retry"

        ClickedEditCheckpoints ->
            "Edit Checkpoints"

        ClickedSaveCheckpoints ->
            "Save Checkpoints"

        ClickedSelectAllCheckpoints ->
            "Select All"

        ClickedClearAllCheckpoints ->
            "Clear All"

        _ ->
            ""



-- JSON Decoders


type alias ScheduleData =
    { checkpointData : List Checkpoint
    , startData : Place
    , finishData : Place
    }


scheduleDecoder : Decoder ScheduleData
scheduleDecoder =
    Decode.succeed ScheduleData
        |> custom checkpointsDecoder
        |> custom startPlaceDecoder
        |> custom finishPlaceDecoder



-- Checkpoints Data


checkpointDataDecoder : Decoder ( List Checkpoint, Set PlaceId )
checkpointDataDecoder =
    Decode.map2 Tuple.pair
        checkpointsDecoder
        checkpointSelectionDecoder


checkpointSelectionDecoder : Decoder (Set PlaceId)
checkpointSelectionDecoder =
    Decode.map2 Tuple.pair
        (Decode.field "saved" Decode.bool)
        (Decode.field "place_id" Decode.string)
        |> Decode.list
        |> Decode.map filteredCheckpointSelection
        |> Decode.field "checkpoints"


filteredCheckpointSelection : List ( Bool, PlaceId ) -> Set PlaceId
filteredCheckpointSelection tupleList =
    List.filter Tuple.first tupleList
        |> List.map Tuple.second
        |> Set.fromList


checkpointsDecoder : Decoder (List Checkpoint)
checkpointsDecoder =
    placeJsonDecoder
        |> Decode.map placeInfoFromPlaceJson
        |> Decode.map Checkpoint
        |> Decode.list
        |> Decode.field "checkpoints"



-- Start


startDataDecoder : Decoder (SelectList Place)
startDataDecoder =
    placeJsonDecoder
        |> Decode.list
        |> Decode.andThen toSelectList
        |> Decode.map (SelectList.map Start)
        |> Decode.field "start"


startPlaceDecoder : Decoder Place
startPlaceDecoder =
    placeJsonDecoder
        |> Decode.map placeInfoFromPlaceJson
        |> Decode.map Start
        |> Decode.list
        |> Decode.map List.head
        |> Decode.andThen failOnEmptyList
        |> Decode.field "start"



-- Finish


finishDataDecoder : Decoder (SelectList Place)
finishDataDecoder =
    placeJsonDecoder
        |> Decode.list
        |> Decode.andThen toSelectList
        |> Decode.map (SelectList.map Finish)
        |> Decode.field "finish"


finishPlaceDecoder : Decoder Place
finishPlaceDecoder =
    placeJsonDecoder
        |> Decode.map placeInfoFromPlaceJson
        |> Decode.map Finish
        |> Decode.list
        |> Decode.map List.head
        |> Decode.andThen failOnEmptyList
        |> Decode.field "finish"



-- Place


toSelectList : List PlaceJson -> Decoder (SelectList PlaceInfo)
toSelectList placeJsonList =
    let
        savedTupleList =
            List.indexedMap Tuple.pair placeJsonList
                |> List.filter (\tuple -> Tuple.second tuple |> .saved)
    in
    case savedTupleList of
        ( savedIndex, savedPlace ) :: [] ->
            SelectList.fromLists
                (List.take savedIndex placeJsonList)
                savedPlace
                (List.drop (savedIndex + 1) placeJsonList)
                |> SelectList.map placeInfoFromPlaceJson
                |> Decode.succeed

        _ ->
            Decode.fail "List of places must contain exactly one saved place."


failOnEmptyList : Maybe Place -> Decoder Place
failOnEmptyList maybePlace =
    case maybePlace of
        Just place ->
            Decode.succeed place

        Nothing ->
            Decode.fail "place list cannot be empty."


type alias PlaceJson =
    { name : String
    , placeType : String
    , altitude : Float
    , schedule : String
    , distance : Float
    , elevationGain : Float
    , elevationLoss : Float
    , coords : Coords
    , placeId : PlaceId
    , saved : Bool
    }


placeInfoFromPlaceJson : PlaceJson -> PlaceInfo
placeInfoFromPlaceJson placeJson =
    PlaceInfo
        placeJson.name
        placeJson.placeType
        placeJson.altitude
        placeJson.schedule
        placeJson.distance
        placeJson.elevationGain
        placeJson.elevationLoss
        placeJson.coords
        placeJson.placeId


placeJsonDecoder : Decoder PlaceJson
placeJsonDecoder =
    Decode.succeed PlaceJson
        |> required "name" Decode.string
        |> required "place_type" Decode.string
        |> required "altitude" Decode.float
        |> required "schedule" Decode.string
        |> required "distance" Decode.float
        |> required "elevation_gain" Decode.float
        |> required "elevation_loss" Decode.float
        |> required "coords" coordsDecoder
        |> required "place_id" Decode.string
        |> required "saved" Decode.bool


coordsDecoder : Decoder Coords
coordsDecoder =
    Decode.succeed Coords
        |> required "lat" Decode.float
        |> required "lng" Decode.float



-- JSON Encoders


checkpointSelectionEncoder : CheckpointSelection -> Value
checkpointSelectionEncoder selection =
    Encode.set Encode.string selection



-- HTTP


getSchedule : String -> Cmd Msg
getSchedule url =
    Http.get
        { url = url
        , expect = Http.expectJson GotSchedule scheduleDecoder
        }


getCheckpoints : String -> Cmd Msg
getCheckpoints url =
    Http.get
        { url = url
        , expect = Http.expectJson GotPossibleCheckpoints checkpointDataDecoder
        }


postCheckpoints : String -> String -> CheckpointSelection -> Cmd Msg
postCheckpoints url csrfToken selection =
    let
        body =
            Encode.object [ ( "checkpoints", checkpointSelectionEncoder selection ) ]
    in
    Http.request
        { method = "POST"
        , headers = [ Http.header "X-CSRFToken" csrfToken ]
        , url = url
        , body = Http.jsonBody body
        , expect = Http.expectJson GotCheckpoints checkpointsDecoder
        , timeout = Nothing
        , tracker = Nothing
        }


getPlace : Place -> String -> Cmd Msg
getPlace place url =
    let
        decoder =
            case place of
                Start _ ->
                    startDataDecoder

                Finish _ ->
                    finishDataDecoder
    in
    Http.get
        { url = url
        , expect = Http.expectJson (GotPossiblePlace place) decoder
        }


postPlace : Place -> String -> String -> PlaceId -> Cmd Msg
postPlace place url csrfToken placeId =
    let
        ( body, decoder ) =
            case place of
                Start _ ->
                    ( Encode.object [ ( "start", Encode.string placeId ) ]
                    , startPlaceDecoder
                    )

                Finish _ ->
                    ( Encode.object [ ( "finish", Encode.string placeId ) ]
                    , finishPlaceDecoder
                    )
    in
    Http.request
        { method = "POST"
        , headers = [ Http.header "X-CSRFToken" csrfToken ]
        , url = url
        , body = Http.jsonBody body
        , expect = Http.expectJson (GotPlace place) decoder
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
